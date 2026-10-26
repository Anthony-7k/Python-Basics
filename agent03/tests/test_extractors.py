from app.document_ai.extractors import classify_document, extract_fields
from app.document_ai.parsers import ParsedPage, TextBlock


def page(*lines: str) -> list[ParsedPage]:
    blocks = [TextBlock(text=line, bbox=[0.0, float(i), 100.0, float(i + 1)]) for i, line in enumerate(lines)]
    return [ParsedPage(page_number=1, text="\n".join(lines), width=100, height=100, blocks=blocks)]


def test_invoice_classification_and_normalization():
    pages = page(
        "增值税发票",
        "发票号码：INV-2026-09",
        "销售方：示例销售公司",
        "税额：123.45",
        "价税合计：1,234.50",
        "开票日期：2026/09/27",
    )
    classification, confidence = classify_document(pages[0].text, "invoice.pdf")
    assert classification == "invoice"
    assert confidence >= 0.9
    fields = {item.field_name: item for item in extract_fields(classification, pages)}
    assert fields["invoice_number"].normalized_value == "INV-2026-09"
    assert fields["total_with_tax"].normalized_value == "1234.50"
    assert fields["invoice_date"].normalized_value == "2026-09-27"


def test_purchase_order_fields():
    pages = page("采购单", "订单号：PO-001", "供应商：示例供应商", "含税总额：2,000")
    classification, _ = classify_document(pages[0].text, "order.docx")
    fields = {item.field_name: item for item in extract_fields(classification, pages)}
    assert classification == "purchase_order"
    assert fields["order_number"].normalized_value == "PO-001"
    assert fields["total_amount"].normalized_value == "2000.00"

