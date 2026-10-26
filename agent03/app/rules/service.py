from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import (
    Document,
    DocumentLink,
    ExtractionRun,
    FieldValue,
    ReviewCase,
    RiskFinding,
    RuleRun,
    utc_now,
)
from app.rag import PolicyRetrievalService
from app.repositories import NotFound, TenantRepository

POLICY_QUERIES = {
    "REQUIRED_DOCUMENTS": "合同 采购单 发票 单据完整性 缺失",
    "SUPPLIER_MATCH": "合同乙方 采购单供应商 发票销售方 交易主体一致",
    "AMOUNT_HIERARCHY": "发票含税金额 采购订单 合同总额 超额",
    "DATE_SEQUENCE": "合同生效日期 发票日期 业务期间",
}


@dataclass(frozen=True)
class ReviewResult:
    run_group_id: str
    rules: int
    risks: int


class CaseReviewService:
    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
        self.repo = TenantRepository(session, tenant_id)

    def run(self, case_id: str) -> ReviewResult:
        case = self.repo.get_case(case_id)
        documents = self._documents(case)
        run_group_id = str(uuid4())
        created_at = utc_now()
        risk_count = 0

        expected = {"contract", "purchase_order", "invoice"}
        counts = {kind: [doc.id for doc in case.documents if doc.classification == kind]
                  for kind in expected}
        ambiguous = {kind: ids for kind, ids in counts.items() if len(ids) > 1}
        missing = sorted(kind for kind in expected if not counts[kind])
        risk_count += self._record_rule(
            case,
            run_group_id,
            "REQUIRED_DOCUMENTS",
            not missing,
            "HIGH",
            "三类业务文档齐全" if not missing else f"缺少文档类型：{', '.join(missing)}",
            {"present": sorted(kind for kind in expected if counts[kind]), "missing": missing},
            [],
            created_at,
        )

        if ambiguous:
            risk_count += self._record_rule(
                case, run_group_id, "AMBIGUOUS_DOCUMENT_SET", False, "HIGH",
                "同类业务文档存在多份，必须人工确认匹配关系，不能自动选取或汇总",
                {"candidates": ambiguous}, [], created_at,
            )

        if not missing and not ambiguous:
            self._create_links(case, documents, run_group_id, created_at)
            risk_count += self._supplier_rule(case, documents, run_group_id, created_at)
            risk_count += self._amount_rule(case, documents, run_group_id, created_at)
            risk_count += self._date_rule(case, documents, run_group_id, created_at)

        self.session.flush()
        rule_count = self.session.query(RuleRun).filter_by(run_group_id=run_group_id).count()
        return ReviewResult(run_group_id, rule_count, risk_count)

    def latest_risks(self, case_id: str) -> list[RiskFinding]:
        group = self.latest_run_group(case_id)
        if group is None:
            raise NotFound("case review not found")
        return list(
            self.session.scalars(
                select(RiskFinding)
                .where(
                    RiskFinding.tenant_id == self.tenant_id,
                    RiskFinding.case_id == case_id,
                    RiskFinding.run_group_id == group,
                )
                .order_by(RiskFinding.severity, RiskFinding.created_at)
            )
        )

    def latest_run_group(self, case_id: str) -> str | None:
        self.repo.get_case(case_id)
        return self.session.scalar(
            select(RuleRun.run_group_id)
            .where(RuleRun.tenant_id == self.tenant_id, RuleRun.case_id == case_id)
            .order_by(RuleRun.created_at.desc())
            .limit(1)
        )

    def comparison(self, case_id: str) -> dict:
        case = self.repo.get_case(case_id)
        documents = self._documents(case)
        columns = []
        for kind in ("contract", "purchase_order", "invoice"):
            entry = documents.get(kind)
            candidates = sorted(
                (doc for doc in case.documents if doc.classification == kind),
                key=lambda doc: doc.id,
            )
            match_status = (
                "AMBIGUOUS" if len(candidates) > 1 else
                "MISSING" if not candidates else
                "MATCHED" if entry else "UNAVAILABLE"
            )
            columns.append(
                {
                    "document_type": kind,
                    "match_status": match_status,
                    "candidates": [
                        {"document_id": doc.id, "original_name": doc.original_name,
                         "parse_status": doc.parse_status}
                        for doc in candidates
                    ],
                    "document_id": entry[0].id if entry else None,
                    "original_name": entry[0].original_name if entry else None,
                    "fields": {
                        name: {
                            "value": field.normalized_value,
                            "confidence": field.confidence,
                            "evidence_id": field.evidence_id,
                        }
                        for name, field in (entry[1].items() if entry else [])
                    },
                }
            )
        return {"case_id": case.id, "columns": columns}

    def _documents(self, case: ReviewCase) -> dict[str, tuple[Document, dict[str, FieldValue]]]:
        result = {}
        counts = {}
        for document in case.documents:
            counts[document.classification] = counts.get(document.classification, 0) + 1
        for document in case.documents:
            if not document.classification or counts[document.classification] != 1:
                continue
            run = self.session.scalars(
                select(ExtractionRun)
                .where(
                    ExtractionRun.tenant_id == self.tenant_id,
                    ExtractionRun.document_id == document.id,
                    ExtractionRun.status == "COMPLETED",
                )
                .options(joinedload(ExtractionRun.fields))
                .order_by(ExtractionRun.created_at.desc())
            ).unique().first()
            if run:
                result[document.classification] = (
                    document,
                    {field.field_name: field for field in run.fields},
                )
        return result

    def _create_links(self, case, documents, group, created_at) -> None:
        for source_kind, target_kind, link_type in (
            ("contract", "purchase_order", "CONTRACT_TO_ORDER"),
            ("purchase_order", "invoice", "ORDER_TO_INVOICE"),
        ):
            source = documents[source_kind][0]
            target = documents[target_kind][0]
            self.session.add(
                DocumentLink(
                    tenant_id=self.tenant_id,
                    case_id=case.id,
                    run_group_id=group,
                    source_document_id=source.id,
                    target_document_id=target.id,
                    link_type=link_type,
                    score=1.0,
                    evidence={"basis": "same_case_and_complete_document_set"},
                    created_at=created_at,
                )
            )

    def _supplier_rule(self, case, documents, group, created_at) -> int:
        fields = [
            documents["contract"][1].get("party_b"),
            documents["purchase_order"][1].get("supplier"),
            documents["invoice"][1].get("seller"),
        ]
        values = [field.normalized_value if field else None for field in fields]
        normalized = [_normalize_party(value) for value in values if value]
        passed = len(normalized) == 3 and len(set(normalized)) == 1
        explanation = "合同乙方、采购单供应商和发票销售方一致" if passed else "交易主体不一致或字段缺失"
        return self._record_rule(
            case, group, "SUPPLIER_MATCH", passed, "HIGH", explanation,
            {"party_b": values[0], "supplier": values[1], "seller": values[2]},
            [field.evidence_id for field in fields if field], created_at,
        )

    def _amount_rule(self, case, documents, group, created_at) -> int:
        contract = documents["contract"][1].get("total_amount")
        order = documents["purchase_order"][1].get("total_amount")
        invoice = documents["invoice"][1].get("total_with_tax")
        fields = [contract, order, invoice]
        amounts = [_decimal(field.normalized_value) if field else None for field in fields]
        passed = all(value is not None for value in amounts)
        if passed:
            passed = amounts[2] <= amounts[1] <= amounts[0]
        explanation = "金额满足 发票小于等于采购单小于等于合同" if passed else "金额超限或关键金额缺失"
        return self._record_rule(
            case, group, "AMOUNT_HIERARCHY", passed, "HIGH", explanation,
            {"contract": _string(amounts[0]), "purchase_order": _string(amounts[1]), "invoice": _string(amounts[2])},
            [field.evidence_id for field in fields if field], created_at,
        )

    def _date_rule(self, case, documents, group, created_at) -> int:
        effective = documents["contract"][1].get("effective_date")
        invoice = documents["invoice"][1].get("invoice_date")
        start = _date(effective.normalized_value) if effective else None
        issued = _date(invoice.normalized_value) if invoice else None
        passed = start is not None and issued is not None and issued >= start
        explanation = "发票日期不早于合同生效日期" if passed else "日期顺序异常或关键日期缺失"
        return self._record_rule(
            case, group, "DATE_SEQUENCE", passed, "MEDIUM", explanation,
            {"effective_date": _string(start), "invoice_date": _string(issued)},
            [field.evidence_id for field in (effective, invoice) if field], created_at,
        )

    def _record_rule(self, case, group, code, passed, severity, explanation, inputs, evidence_ids, created_at) -> int:
        rule = RuleRun(
            tenant_id=self.tenant_id,
            case_id=case.id,
            run_group_id=group,
            rule_code=code,
            outcome="PASS" if passed else "FAIL",
            severity=severity,
            explanation=explanation,
            inputs=inputs,
            evidence_ids=evidence_ids,
            created_at=created_at,
        )
        self.session.add(rule)
        self.session.flush()
        if passed:
            return 0
        self.session.add(
            RiskFinding(
                tenant_id=self.tenant_id,
                case_id=case.id,
                rule_run_id=rule.id,
                run_group_id=group,
                risk_type=code,
                severity=severity,
                explanation=explanation,
                score=1.0 if severity == "HIGH" else 0.6,
                evidence_ids=evidence_ids,
                policy_citations=[
                    citation.as_dict()
                    for citation in PolicyRetrievalService(
                        self.session, self.tenant_id
                    ).search(POLICY_QUERIES.get(code, explanation), limit=3)
                ],
                created_at=created_at,
            )
        )
        return 1


def _normalize_party(value: str) -> str:
    return re.sub(r"[\s（）()\-_.，,。]", "", value).lower()


def _decimal(value: str) -> Decimal | None:
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError):
        return None


def _date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _string(value) -> str | None:
    return str(value) if value is not None else None

