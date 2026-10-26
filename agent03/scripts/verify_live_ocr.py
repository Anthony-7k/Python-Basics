"""Verify only the fictional scan fixtures against the local workbench."""
import json
import time
from pathlib import Path
from uuid import uuid4

import httpx


def verify():
    inputs = Path("eval/results/inputs")
    paths = [inputs / f"{kind}-01-scan.png" for kind in ("contract", "order", "invoice")]
    if not all(path.is_file() for path in paths):
        raise RuntimeError("run evaluate_document_ai.py first to generate fictional scan fixtures")
    with httpx.Client(base_url="http://127.0.0.1:8003", timeout=90) as client:
        login = client.post("/api/v1/auth/login", json={"email": "demo@docflow.local", "password": "Demo123!"})
        login.raise_for_status()
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        response = client.post("/api/v1/cases", json={"title": "真实 OCR 验收 三单扫描图",
                                                     "description": "虚构测试材料；真实 CPU OCR；等待人工核对，不对应真实交易。"})
        response.raise_for_status()
        case_id = response.json()["id"]
        ids = []
        for index, path in enumerate(paths):
            response = client.post(f"/api/v1/cases/{case_id}/documents",
                                   files={"file": (f"scan-{index + 1}.png", path.read_bytes(), "image/png")})
            response.raise_for_status()
            ids.append(response.json()["id"])
        submitted = client.post(f"/api/v1/cases/{case_id}/submit", headers={"Idempotency-Key": str(uuid4())})
        submitted.raise_for_status()
        job_id = submitted.json()["id"]
        deadline = time.monotonic() + 90
        while True:
            response = client.get(f"/api/v1/jobs/{job_id}")
            response.raise_for_status()
            job = response.json()
            if job["status"] in {"SUCCEEDED", "FAILED"} or time.monotonic() > deadline:
                break
            time.sleep(.5)
        if job["status"] != "SUCCEEDED":
            raise RuntimeError(f"OCR job did not succeed: {job['status']}")
        extractions = []
        for document_id in ids:
            response = client.get(f"/api/v1/documents/{document_id}/extraction")
            response.raise_for_status()
            extraction = response.json()
            if extraction["processing_metadata"]["page_methods"] != ["rapidocr"]:
                raise RuntimeError("local workbench is not running real OCR")
            extractions.append({"document_id": document_id, "classification": extraction["classification"],
                                "fields": len(extraction["fields"]), "metadata": extraction["processing_metadata"]})
        response = client.get(f"/api/v1/cases/{case_id}/risks")
        response.raise_for_status()
        if response.json():
            raise RuntimeError("normal fictional scan case unexpectedly produced risks")
        result = {"fictional": True, "case_id": case_id, "job_id": job_id,
                  "status": job["status"], "risks": [], "extractions": extractions}
        Path("eval/results/live-ocr.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    verify()
