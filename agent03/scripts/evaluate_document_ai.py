"""Reproducible synthetic benchmark, not a real-world accuracy claim.

Only fictional fixtures are sent to a configured model; cloud mode is explicit.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from time import perf_counter

import pymupdf
from PIL import Image

from app.config import Settings
from app.document_ai.extractors import classify_document, extract_fields
from app.document_ai.parsers import parse_document
from app.domain import DocumentKind
from app.providers import build_providers


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)] if ordered else None


def score_fields(expected, actual):
    """Missing and extra fields both count; empty references cannot inflate accuracy."""
    correct = sum(actual.get(key) == value for key, value in expected.items())
    return {"correct": correct, "expected": len(expected), "predicted": len(actual)}


def run(fixtures: Path, output: Path, ocr_backend: str, extraction_backend: str):
    manifest = json.loads((fixtures / "审查测试清单.json").read_text(encoding="utf-8"))
    if manifest.get("fictional") is not True:
        raise ValueError("benchmark requires explicitly fictional fixtures")
    settings = Settings(ocr_backend=ocr_backend, extraction_backend=extraction_backend)
    providers = build_providers(settings)
    references = json.loads((Path(__file__).parent.parent / "eval" / "golden.json").read_text(encoding="utf-8"))
    records = []
    work = output.parent / "inputs"
    work.mkdir(parents=True, exist_ok=True)
    for item in references:
        source = (fixtures / item["file"]).resolve()
        if fixtures.resolve() not in source.parents:
            raise ValueError("fixture outside benchmark root")
        with pymupdf.open(source) as document:
            raster = document[0].get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
            image = Image.frombytes("RGB", (raster.width, raster.height), raster.samples)
        variants = [("native", source, DocumentKind.PDF), ("scan", image, DocumentKind.PNG),
                    ("rotated", image.rotate(2, expand=True, fillcolor="white"), DocumentKind.PNG),
                    ("low_resolution", image.resize((image.width // 2, image.height // 2)), DocumentKind.PNG)]
        for variant, value, kind in variants:
            if variant != "native":
                value = value.convert("RGB")
                target = work / f"{item['id']}-{variant}.png"
                value.save(target)
            else:
                target = value
            started = perf_counter()
            row = {"id": item["id"], "variant": variant, "expected_classification": item["classification"],
                   "expected_fields": item["fields"], "status": "ok", "model_usage": None}
            try:
                pages = parse_document(target, kind, "neutral-document", providers.ocr)
                classification, _ = classify_document("\n".join(page.text for page in pages), "neutral-document")
                candidates = extract_fields(classification, pages)
                if providers.extractor is not None:
                    result = providers.extractor.extract(pages)
                    classification, candidates = result.classification, result.fields
                    row["model_usage"] = result.metadata
                actual = {field.field_name: field.normalized_value for field in candidates}
                row.update(classification=classification, actual_fields=actual,
                           field_scores=score_fields(item["fields"], actual),
                           classification_correct=classification == item["classification"],
                           page_methods=[page.method for page in pages])
            except Exception as exc:
                row.update(status="failed", error_type=type(exc).__name__, classification_correct=False,
                           actual_fields={}, field_scores=score_fields(item["fields"], {}))
            row["latency_ms"] = round((perf_counter() - started) * 1000, 2)
            records.append(row)
    groups = {}
    for variant in ("native", "scan", "rotated", "low_resolution"):
        rows = [row for row in records if row["variant"] == variant]
        correct = sum(row["field_scores"]["correct"] for row in rows)
        expected = sum(row["field_scores"]["expected"] for row in rows)
        predicted = sum(row["field_scores"]["predicted"] for row in rows)
        latency = [row["latency_ms"] for row in rows]
        groups[variant] = {"samples": len(rows), "failures": sum(row["status"] != "ok" for row in rows),
                           "classification_accuracy": sum(row["classification_correct"] for row in rows) / len(rows),
                           "field_precision": correct / predicted if predicted else 0,
                           "field_recall": correct / expected if expected else 0,
                           "mean_latency_ms": round(statistics.mean(latency), 2),
                           "p95_latency_ms": percentile(latency, .95)}
    report = {"dataset": "synthetic-docflow-v1", "warning": "Synthetic raster variants are correlated; not real-world OCR accuracy.",
              "ocr_backend": ocr_backend, "extraction_backend": extraction_backend,
              "groups": groups, "records": records}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(groups, ensure_ascii=True))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", type=Path, default=Path("tests/fixtures/demo"))
    parser.add_argument("--output", type=Path, default=Path("eval/results/document-ai.json"))
    parser.add_argument("--ocr", choices=["fake", "rapidocr"], default="rapidocr")
    parser.add_argument("--extractor", choices=["deterministic", "ollama", "cloud"], default="deterministic")
    args = parser.parse_args()
    run(args.fixtures, args.output, args.ocr, args.extractor)
