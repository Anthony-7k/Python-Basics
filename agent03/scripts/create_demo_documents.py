"""Create clearly fictional, reproducible PDF review fixtures without overwriting files."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

SELLER = "星河测试设备有限公司"
BUYER = "晨曦测试采购有限公司"


def scenarios():
    return [
        {"folder": "01_正常三单", "title": "模拟审查 正常三单", "expected": [], "amount": "100000.00", "seller": SELLER, "date": "2026-09-25", "invoices": 1},
        {"folder": "02_金额超限", "title": "模拟审查 金额超限", "expected": ["AMOUNT_HIERARCHY"], "amount": "125000.00", "seller": SELLER, "date": "2026-09-25", "invoices": 1},
        {"folder": "03_主体与日期异常", "title": "模拟审查 主体与日期异常", "expected": ["SUPPLIER_MATCH", "DATE_SEQUENCE"], "amount": "100000.00", "seller": "远航测试贸易有限公司", "date": "2026-08-20", "invoices": 1},
        {"folder": "04_缺少发票", "title": "模拟审查 缺少发票", "expected": ["REQUIRED_DOCUMENTS"], "amount": "100000.00", "seller": SELLER, "date": "2026-09-25", "invoices": 0},
        {"folder": "05_多发票待人工匹配", "title": "模拟审查 多发票待人工匹配", "expected": ["AMBIGUOUS_DOCUMENT_SET"], "amount": "100000.00", "seller": SELLER, "date": "2026-09-25", "invoices": 2},
    ]


def render_pdf(path: Path, title: str, fields: list[tuple[str, str]], reference: str):
    pdf = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    pdf.setTitle(title + " 模拟测试材料")
    pdf.setAuthor("DocFlow AI Test Fixtures")
    width, height = A4
    pdf.setFont("STSong-Light", 10)
    pdf.setFillColor(colors.HexColor("#666666"))
    pdf.drawString(50, height - 48, "DocFlow AI 模拟测试材料")
    pdf.setFillColor(colors.black)
    pdf.setFont("STSong-Light", 23)
    pdf.drawString(50, height - 90, title)
    pdf.setFont("STSong-Light", 11)
    pdf.drawString(50, height - 118, "本文件及所列企业均为虚构，仅供软件审查测试，无交易或法律效力。")
    pdf.setStrokeColor(colors.HexColor("#d9d9d9"))
    pdf.line(50, height - 135, width - 50, height - 135)
    y = height - 177
    pdf.setFont("STSong-Light", 12)
    for label, value in fields:
        pdf.drawString(55, y, f"{label}：{value}")
        y -= 34
    y -= 12
    pdf.setFont("STSong-Light", 13)
    pdf.drawString(55, y, "业务说明")
    pdf.setFont("STSong-Light", 11)
    for line in ["测试货物为办公设备一批，金额单位为人民币。", reference,
                 "数量及金额由虚构业务场景设定，不对应任何真实采购。",
                 "经办人：测试经办员    审核人：测试审核员"]:
        y -= 26
        pdf.drawString(55, y, line)
    pdf.setFont("STSong-Light", 9)
    pdf.setFillColor(colors.HexColor("#666666"))
    pdf.drawString(50, 38, "虚构测试数据  不可用于报销或真实交易")
    pdf.drawRightString(width - 50, 38, "1 / 1")
    pdf.save()


def create(root: Path):
    entries = scenarios()
    destinations = [root / item["folder"] for item in entries]
    if any(path.exists() for path in destinations) or (root / "审查测试清单.json").exists():
        raise FileExistsError("Demo outputs already exist; refusing to overwrite")
    root.mkdir(parents=True, exist_ok=True)
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    for index, item in enumerate(entries, 1):
        directory = root / item["folder"]
        directory.mkdir()
        prefix = f"DEMO-{index:02d}"
        contract = directory / "采购合同.pdf"
        order = directory / "采购单.pdf"
        render_pdf(contract, "设备采购合同", [
            ("合同编号", f"HT-{prefix}"), ("甲方", BUYER), ("乙方", SELLER),
            ("合同总额", "120000.00"), ("生效日期", "2026-09-01")], "交付事项按本批采购需求执行。")
        render_pdf(order, "设备采购单", [
            ("采购单号", f"PO-{prefix}"), ("供应商", SELLER),
            ("订单总额", "100000.00"), ("采购日期", "2026-09-15")], "同批货物为办公设备一批。")
        files = [str(contract.relative_to(root)), str(order.relative_to(root))]
        for number in range(1, item["invoices"] + 1):
            invoice = directory / ("模拟发票.pdf" if item["invoices"] == 1 else f"模拟发票_{number}.pdf")
            render_pdf(invoice, "销售发票模拟样本", [
                ("发票号码", f"INV-{prefix}-{number}"), ("销售方", item["seller"]),
                ("税额", "11504.42"), ("价税合计", item["amount"]),
                ("开票日期", item["date"])], "非税务发票，无票据效力，仅用于系统测试。")
            files.append(str(invoice.relative_to(root)))
        item["files"] = files
    manifest = {"fictional": True, "cases": entries}
    (root / "审查测试清单.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    instructions = "DocFlow AI 模拟文档使用说明\n\n所有企业、单号和交易均为虚构测试数据。\n每个子文件夹单独新建一个案件，只上传该子文件夹的 PDF。\n不要将所有子文件夹混入同一个案件。\n\n" + "\n".join(f"{item['folder']}：预期风险 {', '.join(item['expected']) or '无'}" for item in entries)
    (root / "使用说明.txt").write_text(instructions, encoding="utf-8")
    print(json.dumps({"root": str(root), "cases": len(entries), "pdf_count": sum(len(item["files"]) for item in entries)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    create(parser.parse_args().output)
