from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.document_ai.parsers import ParsedPage, TextBlock


@dataclass(frozen=True)
class FieldCandidate:
    field_name: str
    raw_value: str
    normalized_value: str
    confidence: float
    page_number: int
    bbox: list[float]
    snippet: str


PATTERNS: dict[str, list[tuple[str, str, str]]] = {
    "contract": [
        ("contract_number", r"合同(?:编号|号)\s*[:：]?\s*([A-Za-z0-9_-]+)", "text"),
        ("party_a", r"甲方\s*[:：]?\s*([^\n|]{2,80})", "text"),
        ("party_b", r"乙方\s*[:：]?\s*([^\n|]{2,80})", "text"),
        ("total_amount", r"(?:合同总额|合同金额)\s*[:：]?\s*(?:人民币|[¥￥])?\s*([0-9,]+(?:\.[0-9]{1,2})?)", "amount"),
        ("effective_date", r"(?:生效日期|签订日期)\s*[:：]?\s*(\d{4}[-年/]\d{1,2}[-月/]\d{1,2}日?)", "date"),
    ],
    "purchase_order": [
        ("order_number", r"(?:采购单号|订单号)\s*[:：]?\s*([A-Za-z0-9_-]+)", "text"),
        ("supplier", r"供应商\s*[:：]?\s*([^\n|]{2,80})", "text"),
        ("total_amount", r"(?:含税总额|订单总额)\s*[:：]?\s*(?:人民币|[¥￥])?\s*([0-9,]+(?:\.[0-9]{1,2})?)", "amount"),
    ],
    "invoice": [
        ("invoice_number", r"发票(?:号码|号)\s*[:：]?\s*([A-Za-z0-9_-]+)", "text"),
        ("seller", r"(?:销售方|销方)\s*[:：]?\s*([^\n|]{2,80})", "text"),
        ("tax_amount", r"税额\s*[:：]?\s*(?:人民币|[¥￥])?\s*([0-9,]+(?:\.[0-9]{1,2})?)", "amount"),
        ("total_with_tax", r"(?:价税合计|含税金额)\s*[:：]?\s*(?:人民币|[¥￥])?\s*([0-9,]+(?:\.[0-9]{1,2})?)", "amount"),
        ("invoice_date", r"开票日期\s*[:：]?\s*(\d{4}[-年/]\d{1,2}[-月/]\d{1,2}日?)", "date"),
    ],
}


def classify_document(text: str, original_name: str) -> tuple[str, float]:
    value = f"{original_name}\n{text}".lower()
    scores = {
        "invoice": sum(token in value for token in ("发票", "价税合计", "开票日期")),
        "purchase_order": sum(token in value for token in ("采购单", "订单号", "供应商")),
        "contract": sum(token in value for token in ("合同", "甲方", "乙方")),
    }
    label, score = max(scores.items(), key=lambda item: item[1])
    if score == 0:
        return "unknown", 0.35
    return label, min(0.99, 0.70 + score * 0.09)


def extract_fields(classification: str, pages: list[ParsedPage]) -> list[FieldCandidate]:
    candidates = []
    for field_name, pattern, normalizer in PATTERNS.get(classification, []):
        found = _find(pattern, pages)
        if found is None:
            continue
        raw, page_number, block = found
        candidates.append(
            FieldCandidate(
                field_name=field_name,
                raw_value=raw,
                normalized_value=_normalize(raw, normalizer),
                confidence=min(0.98, block.confidence),
                page_number=page_number,
                bbox=block.bbox,
                snippet=block.text[:500],
            )
        )
    return candidates


def _find(pattern: str, pages: list[ParsedPage]) -> tuple[str, int, TextBlock] | None:
    compiled = re.compile(pattern, re.IGNORECASE)
    for page in pages:
        for block in page.blocks:
            match = compiled.search(block.text)
            if match:
                return match.group(1).strip(), page.page_number, block
    return None


def _normalize(value: str, kind: str) -> str:
    if kind == "amount":
        try:
            return format(Decimal(value.replace(",", "")).quantize(Decimal("0.01")), "f")
        except InvalidOperation:
            return value.strip()
    if kind == "date":
        compact = value.replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-")
        try:
            return datetime.strptime(compact, "%Y-%m-%d").date().isoformat()
        except ValueError:
            return value.strip()
    return value.strip()

