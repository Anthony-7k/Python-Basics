import importlib.util
import json
from io import BytesIO

import httpx
import pymupdf
import pytest
from PIL import Image

from app.config import Settings
from app.document_ai.parsers import ParsedPage, TextBlock, parse_document
from app.domain import DocumentKind
from app.providers.model_extraction import OllamaExtractor
from scripts.evaluate_document_ai import score_fields


def pages():
    return [ParsedPage(1, "合同总额：1200.00", 200, 200,
                       [TextBlock("合同总额：1200.00", [1, 2, 100, 20], .91)])]


def response(document, **extra):
    return httpx.Response(200, json={"done": True, "message": {"content": json.dumps(document)},
                                     "prompt_eval_count": 100, "eval_count": 20, **extra})


def good():
    return {"classification": "contract", "fields": [
        {"field_name": "total_amount", "raw_value": "1200.00", "block_id": "p1b0"}]}


def test_model_fields_are_grounded_and_usage_recorded():
    def handler(request):
        body = json.loads(request.content)
        assert body["stream"] is False
        assert body["format"]["additionalProperties"] is False
        assert "untrusted" in body["messages"][0]["content"]
        return response(good())
    result = OllamaExtractor("http://localhost", "test", transport=httpx.MockTransport(handler)).extract(pages())
    assert result.fields[0].normalized_value == "1200.00"
    assert result.fields[0].bbox == [1, 2, 100, 20]
    assert result.metadata["input_tokens"] == 100
    assert result.metadata["cost"] is None


@pytest.mark.parametrize("change", ["hallucinated", "unknown_field", "invalid_block", "duplicate", "extra_key"])
def test_model_rejects_unsafe_outputs(change):
    document = good()
    if change == "hallucinated":
        document["fields"][0]["raw_value"] = "999999"
    elif change == "unknown_field":
        document["fields"][0]["field_name"] = "approve_case"
    elif change == "invalid_block":
        document["fields"][0]["block_id"] = "other-tenant"
    elif change == "duplicate":
        document["fields"].append(document["fields"][0].copy())
    else:
        document["execute"] = "approve"
    provider = OllamaExtractor("http://localhost", "test", transport=httpx.MockTransport(lambda _: response(document)))
    with pytest.raises(ValueError):
        provider.extract(pages())


def test_cloud_wire_format_and_secret_handling():
    def handler(request):
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer dummy-test-secret"
        assert json.loads(request.content)["response_format"] == {"type": "json_object"}
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {
            "content": json.dumps(good())}}], "usage": {"prompt_tokens": 101, "completion_tokens": 21}})
    provider = OllamaExtractor("https://example.com/v1", "test", api_key="dummy-test-secret",
                               transport=httpx.MockTransport(handler))
    result = provider.extract(pages())
    assert result.metadata["provider"] == "cloud"
    assert result.metadata["output_tokens"] == 21
    assert "dummy-test-secret" not in json.dumps(result.metadata)
    assert "dummy-test-secret" not in repr(Settings(cloud_model_api_key="dummy-test-secret"))


@pytest.mark.parametrize("status", [401, 429, 503])
def test_model_failure_never_silently_falls_back(status):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status)
    with pytest.raises(RuntimeError, match="no fallback"):
        OllamaExtractor("http://localhost", "test", retries=1,
                        transport=httpx.MockTransport(handler)).extract(pages())
    assert len(calls) == (1 if status == 401 else 2)


def test_scanned_pdf_uses_ocr_and_rescales_evidence(tmp_path):
    image = Image.new("RGB", (300, 400), "white")
    stream = BytesIO()
    image.save(stream, format="PNG")
    pdf = pymupdf.open()
    page = pdf.new_page(width=300, height=400)
    page.insert_image(page.rect, stream=stream.getvalue())
    path = tmp_path / "scan.pdf"
    pdf.save(path)
    pdf.close()
    class OCR:
        def recognize(self, payload):
            assert payload.startswith(b"\x89PNG")
            return [TextBlock("合同总额：1200.00", [25, 50, 250, 100], .9)]
    result = parse_document(path, DocumentKind.PDF, "scan.pdf", OCR())[0]
    assert result.method == "rapidocr"
    assert result.blocks[0].bbox == [10, 20, 100, 40]
    assert result.blocks[0].confidence == .9


def test_cloud_configuration_requires_secure_endpoint_and_credentials():
    with pytest.raises(ValueError, match="HTTPS"):
        Settings(_env_file=None, extraction_backend="cloud", cloud_model_base_url="http://example.com").validate_runtime()
    with pytest.raises(ValueError, match="API key"):
        Settings(_env_file=None, extraction_backend="cloud", cloud_model_base_url="https://example.com").validate_runtime()
    with pytest.raises(ValueError, match="HTTPS"):
        Settings(_env_file=None, extraction_backend="cloud", cloud_model_base_url="https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
                 cloud_model_name="qwen-plus", cloud_model_api_key="dummy-test-only").validate_runtime()


@pytest.mark.parametrize("available", [True, False])
def test_model_pipeline_persists_provenance_or_fails_explicitly(client, auth, app, available):
    from dataclasses import replace
    from pathlib import Path

    def handler(request):
        if not available:
            return httpx.Response(503)
        blocks = json.loads(json.loads(request.content)["messages"][1]["content"])
        block_id = next(block["block_id"] for block in blocks if "合同总额" in block["text"])
        document = good()
        document["fields"][0].update(raw_value="120000.00", block_id=block_id)
        return response(document)

    app.state.providers = replace(app.state.providers, extractor=OllamaExtractor(
        "http://localhost", "test-model", retries=0, transport=httpx.MockTransport(handler)))
    created = client.post("/api/v1/cases", headers=auth, json={"title": "模型处理回归"}).json()
    path = Path(__file__).parent / "fixtures" / "demo" / "01_正常三单" / "采购合同.pdf"
    uploaded = client.post(f"/api/v1/cases/{created['id']}/documents", headers=auth,
                           files={"file": (path.name, path.read_bytes(), "application/pdf")}).json()
    submitted = client.post(f"/api/v1/cases/{created['id']}/submit",
                            headers={**auth, "Idempotency-Key": "model-pipeline"}).json()
    job = client.get(f"/api/v1/jobs/{submitted['id']}", headers=auth).json()
    assert job["status"] == ("SUCCEEDED" if available else "FAILED")
    if available:
        extraction = client.get(f"/api/v1/documents/{uploaded['id']}/extraction", headers=auth).json()
        assert extraction["extractor_version"] == "ollama-grounded-v1"
        assert extraction["processing_metadata"]["model"] == "test-model"
        assert extraction["processing_metadata"]["input_tokens"] == 100
        assert extraction["fields"][0]["source"] == "MODEL"
    else:
        assert job["error_code"] == "RuntimeError"
        assert "no fallback" in job["error_message"]


def test_evaluation_penalizes_missing_and_extra_fields():
    assert score_fields({"a": "1", "b": "2"}, {"a": "1", "fake": "3"}) == {
        "correct": 1, "expected": 2, "predicted": 2}


def test_dashscope_disables_thinking_and_records_service():
    def handler(request):
        body = json.loads(request.content)
        assert body["enable_thinking"] is False
        assert body["response_format"] == {"type": "json_object"}
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {
            "content": json.dumps(good())}}]})
    provider = OllamaExtractor("https://example.com/compatible-mode/v1", "qwen-plus",
                               api_key="test-only", cloud_provider="dashscope",
                               transport=httpx.MockTransport(handler))
    assert provider.extract(pages()).metadata["cloud_service"] == "dashscope"


@pytest.mark.skipif(importlib.util.find_spec("rapidocr") is None, reason="optional real OCR not installed")
def test_real_ocr_image_and_scanned_pdf_end_to_end(client, auth, app):
    from dataclasses import replace
    from pathlib import Path

    from app.providers.ocr import RapidOCRProvider

    app.state.providers = replace(app.state.providers, ocr=RapidOCRProvider())
    case_id = client.post("/api/v1/cases", headers=auth, json={"title": "真实 OCR 三单"}).json()["id"]
    paths = ["采购合同.pdf", "采购单.pdf", "模拟发票.pdf"]
    ids = []
    for index, name in enumerate(paths):
        with pymupdf.open(Path(__file__).parent / "fixtures" / "demo" / "01_正常三单" / name) as source:
            image = source[0].get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False).tobytes("png")
            if index == 1:
                scan = pymupdf.open()
                page = scan.new_page(width=source[0].rect.width, height=source[0].rect.height)
                page.insert_image(page.rect, stream=image)
                image = scan.tobytes()
                scan.close()
        filename, mime = ("neutral.pdf", "application/pdf") if index == 1 else ("neutral.png", "image/png")
        uploaded = client.post(f"/api/v1/cases/{case_id}/documents", headers=auth,
                               files={"file": (filename, image, mime)})
        assert uploaded.status_code == 201
        ids.append(uploaded.json()["id"])
    submitted = client.post(f"/api/v1/cases/{case_id}/submit", headers={**auth, "Idempotency-Key": "real-ocr"})
    job = client.get(f"/api/v1/jobs/{submitted.json()['id']}", headers=auth).json()
    assert job["status"] == "SUCCEEDED", job
    assert client.get(f"/api/v1/cases/{case_id}/risks", headers=auth).json() == []
    for document_id in ids:
        extraction = client.get(f"/api/v1/documents/{document_id}/extraction", headers=auth).json()
        assert extraction["processing_metadata"]["page_methods"] == ["rapidocr"]
        assert extraction["fields"]
