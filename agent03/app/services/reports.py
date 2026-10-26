from __future__ import annotations

import hashlib
import html
import tempfile
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Approval, AuditLog, Report, RiskFinding, RuleRun, utc_now
from app.domain import CaseStatus
from app.providers import ProviderBundle
from app.repositories import TenantRepository
from app.services.errors import Conflict, InvalidInput


class ReportService:
    def __init__(
        self,
        session: Session,
        tenant_id: str,
        actor_id: str,
        providers: ProviderBundle,
    ):
        self.session = session
        self.tenant_id = tenant_id
        self.actor_id = actor_id
        self.providers = providers
        self.repo = TenantRepository(session, tenant_id)

    def request(
        self,
        case_id: str,
        expected_version: int,
        idempotency_key: str,
        trace_id: str,
    ) -> tuple[Report, bool]:
        if not idempotency_key.strip() or len(idempotency_key) > 200:
            raise InvalidInput("Idempotency-Key must contain 1 to 200 characters")
        request_hash = hashlib.sha256(
            f"report:{case_id}:{expected_version}".encode()
        ).hexdigest()
        existing = self.repo.find_report_by_idempotency(idempotency_key)
        if existing:
            if existing.request_hash != request_hash:
                raise Conflict("idempotency key was already used for a different report")
            return existing, False
        case = self.repo.get_case(case_id)
        if case.version != expected_version:
            raise Conflict("case version conflict; refresh and try again")
        if CaseStatus(case.status) != CaseStatus.APPROVED:
            raise Conflict("only approved cases can produce reports")
        prior = self.session.scalar(
            select(Report).where(
                Report.tenant_id == self.tenant_id,
                Report.case_id == case.id,
                Report.case_version == case.version,
            )
        )
        if prior:
            return prior, False
        report = Report(
            tenant_id=self.tenant_id,
            case_id=case.id,
            case_version=case.version,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            trace_id=trace_id,
            created_by=self.actor_id,
        )
        self.session.add(report)
        try:
            self.session.flush()
        except IntegrityError as exc:
            self.session.rollback()
            raced = self.repo.find_report_by_idempotency(idempotency_key)
            if raced and raced.request_hash == request_hash:
                return raced, False
            raise Conflict("report request conflict") from exc
        self.session.add(
            AuditLog(
                tenant_id=self.tenant_id,
                actor_id=self.actor_id,
                action="report.request",
                resource_type="report",
                resource_id=report.id,
                outcome="success",
                trace_id=trace_id,
                after={"case_id": case.id, "case_version": case.version},
            )
        )
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raced = self.repo.find_report_by_idempotency(idempotency_key)
            if raced and raced.request_hash == request_hash:
                return raced, False
            raise Conflict("report request conflict") from exc
        self.providers.queue.enqueue_report(report.id)
        return report, True

    def generate(self, report_id: str) -> Report:
        report = self.repo.get_report(report_id)
        if report.status == "READY":
            return report
        if report.status not in {"QUEUED", "FAILED"}:
            raise Conflict("report is already being generated")
        claimed = self.session.execute(update(Report).where(
            Report.id == report_id, Report.tenant_id == self.tenant_id,
            Report.status.in_(["QUEUED", "FAILED"])
        ).values(status="PROCESSING", error_message=None))
        if claimed.rowcount != 1:
            self.session.rollback()
            raise Conflict("report is already being generated")
        self.session.commit()
        try:
            report = self.repo.get_report(report_id)
            case = self.repo.get_case(report.case_id)
            approval = self.session.scalar(
                select(Approval)
                .where(Approval.tenant_id == self.tenant_id, Approval.case_id == case.id)
                .order_by(Approval.created_at.desc())
            )
            group = self.session.scalar(
                select(RuleRun.run_group_id)
                .where(RuleRun.tenant_id == self.tenant_id, RuleRun.case_id == case.id)
                .order_by(RuleRun.created_at.desc())
                .limit(1)
            )
            risks = list(
                self.session.scalars(
                    select(RiskFinding)
                    .where(
                        RiskFinding.tenant_id == self.tenant_id,
                        RiskFinding.case_id == case.id,
                        RiskFinding.run_group_id == group,
                    )
                    .order_by(RiskFinding.severity, RiskFinding.risk_type)
                )
            ) if group else []
            content = _render_html(case, approval, risks, self.repo)
            artifact = self.providers.report_renderer.render(content)
            payload = artifact.payload
            object_key = f"{self.tenant_id}/reports/{report.id}.{artifact.extension}"
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=f".{artifact.extension}"
            ) as target:
                target.write(artifact.payload)
                temp_path = Path(target.name)
            try:
                self.providers.storage.put(temp_path, object_key)
            finally:
                temp_path.unlink(missing_ok=True)
            report.object_key = object_key
            report.content_hash = hashlib.sha256(payload).hexdigest()
            report.content_type = artifact.content_type
            report.status = "READY"
            report.generated_at = utc_now()
            self.session.add(
                AuditLog(
                    tenant_id=self.tenant_id,
                    actor_id=self.actor_id,
                    action="report.generate",
                    resource_type="report",
                    resource_id=report.id,
                    outcome="success",
                    trace_id=report.trace_id,
                    after={"content_hash": report.content_hash, "object_key": object_key},
                )
            )
            self.session.commit()
            return report
        except Exception as exc:
            self.session.rollback()
            report = self.repo.get_report(report_id)
            report.status = "FAILED"
            report.error_message = str(exc)[:1000]
            self.session.commit()
            raise

    def retry(self, report_id: str, trace_id: str) -> Report:
        report = self.repo.get_report(report_id)
        if report.status != "FAILED":
            raise Conflict("only failed reports can be retried")
        claimed = self.session.execute(update(Report).where(
            Report.id == report.id, Report.tenant_id == self.tenant_id,
            Report.status == "FAILED"
        ).values(status="QUEUED", error_message=None))
        if claimed.rowcount != 1:
            self.session.rollback()
            raise Conflict("report retry conflict")
        self.session.add(AuditLog(
            tenant_id=self.tenant_id, actor_id=self.actor_id, action="report.retry",
            resource_type="report", resource_id=report.id, outcome="success",
            trace_id=trace_id, after={"status": "QUEUED"},
        ))
        self.session.commit()
        self.providers.queue.enqueue_report(report.id)
        return report


def _render_html(case, approval, risks, repo: TenantRepository) -> str:
    documents = []
    for document in case.documents:
        try:
            extraction = repo.get_latest_extraction(document.id)
            fields = "".join(
                f"<tr><td>{html.escape(field.field_name)}</td><td>{html.escape(field.normalized_value)}</td><td>{field.confidence:.0%}</td><td>{html.escape(field.source)}</td><td>第 {field.evidence.page_number} 页：{html.escape(field.evidence.snippet)}</td></tr>"
                for field in extraction.fields
            )
        except LookupError:
            fields = '<tr><td colspan="5">无抽取结果</td></tr>'
        documents.append(
            f"<h3>{html.escape(document.original_name)}</h3><p>类型：{html.escape(document.classification or 'unknown')}</p><table><thead><tr><th>字段</th><th>值</th><th>置信度</th><th>来源</th><th>原文证据</th></tr></thead><tbody>{fields}</tbody></table>"
        )
    risk_rows = "".join(
        f"<tr><td>{html.escape(risk.severity)}</td><td>{html.escape(risk.risk_type)}</td><td>{html.escape(risk.status)}</td><td>{html.escape(risk.explanation)}{_citation_html(risk.policy_citations)}</td></tr>"
        for risk in risks
    ) or '<tr><td colspan="4">未发现风险</td></tr>'
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>DocFlow AI 审查报告</title><style>body{{font-family:Arial,'Microsoft YaHei',sans-serif;max-width:960px;margin:40px auto;color:#172b3a;line-height:1.6}}h1,h2,h3{{color:#102d3d}}table{{width:100%;border-collapse:collapse;margin:12px 0 24px}}th,td{{border:1px solid #d8e0e4;padding:8px;text-align:left}}th{{background:#eaf3f2}}.meta{{color:#526b78}}</style></head><body><h1>DocFlow AI 审查报告</h1><p class="meta">案件编号：{case.id}<br>案件版本：{case.version}<br>报告生成时间：{utc_now().isoformat()}</p><h2>{html.escape(case.title)}</h2><p>{html.escape(case.description)}</p><h2>审批结论</h2><p>{html.escape(approval.decision if approval else 'UNKNOWN')}：{html.escape(approval.reason if approval else '无')}</p><h2>文档与字段</h2>{''.join(documents)}<h2>风险结论</h2><table><thead><tr><th>级别</th><th>类型</th><th>状态</th><th>说明</th></tr></thead><tbody>{risk_rows}</tbody></table></body></html>"""


def _citation_html(citations: list[dict]) -> str:
    if not citations:
        return ""
    items = "".join(
        f"<li>{html.escape(str(item.get('policy_title', '')))} v{html.escape(str(item.get('policy_version', '')))}，第 {int(item.get('page_number', 0))} 页：{html.escape(str(item.get('excerpt', '')))}</li>"
        for item in citations
    )
    return f"<ul>{items}</ul>"
