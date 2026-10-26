"""Run explicitly fictional demo files through the live local HTTP workflow."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from uuid import uuid4

import httpx


def review(root: Path, result_path: Path, base_url: str):
    manifest = json.loads((root / "审查测试清单.json").read_text(encoding="utf-8"))
    if not manifest.get("fictional"):
        raise ValueError("only explicitly fictional manifests may be reviewed")
    output = []
    with httpx.Client(base_url=base_url, timeout=60) as client:
        login = client.post("/api/v1/auth/login", json={"email": "demo@docflow.local", "password": "Demo123!"})
        login.raise_for_status()
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        for scenario in manifest["cases"]:
            created = client.post("/api/v1/cases", json={"title": scenario["title"], "description": "虚构 PDF 端到端验收，不对应真实业务。"})
            created.raise_for_status()
            case_id = created.json()["id"]
            fields = {}
            for relative in scenario["files"]:
                path = (root / relative).resolve()
                if root.resolve() not in path.parents:
                    raise ValueError("manifest contains a path outside the demo folder")
                with path.open("rb") as source:
                    uploaded = client.post(f"/api/v1/cases/{case_id}/documents", files={"file": (path.name, source, "application/pdf")})
                uploaded.raise_for_status()
                fields[uploaded.json()["id"]] = path.name
            submitted = client.post(f"/api/v1/cases/{case_id}/submit", headers={"Idempotency-Key": str(uuid4())})
            submitted.raise_for_status()
            job_id = submitted.json()["id"]
            deadline = time.monotonic() + 60
            job = client.get(f"/api/v1/jobs/{job_id}").json()
            while job["status"] not in {"SUCCEEDED", "FAILED"} and time.monotonic() < deadline:
                time.sleep(0.25)
                job = client.get(f"/api/v1/jobs/{job_id}").json()
            if job["status"] != "SUCCEEDED":
                raise RuntimeError(f"job {job_id}: {job}")
            risks_response = client.get(f"/api/v1/cases/{case_id}/risks")
            risks_response.raise_for_status()
            risks = risks_response.json()
            actual = sorted(risk["risk_type"] for risk in risks)
            extracted = []
            for document_id, filename in fields.items():
                response = client.get(f"/api/v1/documents/{document_id}/extraction")
                response.raise_for_status()
                extraction = response.json()
                extracted.append({"filename": filename, "document_id": document_id, "classification": extraction["classification"], "fields": {field["field_name"]: field["normalized_value"] for field in extraction["fields"]}})
            approval_response = None
            if actual == sorted(scenario["expected"]):
                approval_response = client.post(f"/api/v1/cases/{case_id}/approvals", json={"expected_version": client.get(f"/api/v1/cases/{case_id}").json()["version"], "decision": "APPROVED", "reason": "模拟材料自动验收，验证高风险审批阻断。"})
            report_id = None
            if not scenario["expected"] and approval_response is not None and approval_response.status_code == 201:
                current = client.get(f"/api/v1/cases/{case_id}").json()
                response = client.post(f"/api/v1/cases/{case_id}/reports", headers={"Idempotency-Key": str(uuid4())}, json={"expected_version": current["version"]})
                response.raise_for_status()
                report_id = response.json()["id"]
                deadline = time.monotonic() + 60
                report = client.get(f"/api/v1/reports/{report_id}").json()
                while report["status"] not in {"READY", "FAILED"} and time.monotonic() < deadline:
                    time.sleep(0.5)
                    report = client.get(f"/api/v1/reports/{report_id}").json()
                if report["status"] != "READY":
                    raise RuntimeError(f"report {report_id}: {report}")
                downloaded = client.get(f"/api/v1/reports/{report_id}/download")
                downloaded.raise_for_status()
                if not downloaded.content.startswith(b"%PDF-"):
                    raise ValueError("downloaded report is not PDF")
                result_path.parent.mkdir(parents=True, exist_ok=True)
                (result_path.parent / f"verified-report-{case_id}.pdf").write_bytes(downloaded.content)
            output.append({"title": scenario["title"], "case_id": case_id, "job_id": job_id,
                "expected_risks": scenario["expected"], "actual_risks": actual,
                "matched": actual == sorted(scenario["expected"]), "approval_status": approval_response.status_code if approval_response is not None else None,
                "extractions": extracted, "report_id": report_id})
            result_path.parent.mkdir(parents=True, exist_ok=True)
            result_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps([{key: item[key] for key in ("title", "case_id", "actual_risks", "matched", "approval_status")} for item in output], ensure_ascii=True))
    if not all(item["matched"] and item["approval_status"] == (409 if item["expected_risks"] else 201) for item in output):
        raise RuntimeError("demo risk or approval expectations did not match; inspect results")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--url", default="http://127.0.0.1:8003")
    args = parser.parse_args()
    review(args.root, args.result, args.url)
