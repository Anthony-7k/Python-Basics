"""Regression against the exact Chinese PDF materials used for live acceptance."""
import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "demo"
SCENARIOS = json.loads((FIXTURES / "审查测试清单.json").read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[str(i) for i in range(1, 6)])
def test_chinese_pdf_review_and_approval(client, auth, scenario):
    response = client.post("/api/v1/cases", headers=auth, json={"title": scenario["title"]})
    assert response.status_code == 201
    case_id = response.json()["id"]
    for relative in scenario["files"]:
        path = FIXTURES / relative
        response = client.post(f"/api/v1/cases/{case_id}/documents", headers=auth,
                               files={"file": (path.name, path.read_bytes(), "application/pdf")})
        assert response.status_code == 201, response.text
    response = client.post(f"/api/v1/cases/{case_id}/submit",
                           headers={**auth, "Idempotency-Key": f"demo-{case_id}"})
    assert response.status_code == 202
    job_id = response.json()["id"]
    assert client.get(f"/api/v1/jobs/{job_id}", headers=auth).json()["status"] == "SUCCEEDED"
    risks = client.get(f"/api/v1/cases/{case_id}/risks", headers=auth).json()
    assert sorted(risk["risk_type"] for risk in risks) == sorted(scenario["expected"])
    case = client.get(f"/api/v1/cases/{case_id}", headers=auth).json()
    for document in case["documents"]:
        extraction = client.get(f"/api/v1/documents/{document['id']}/extraction", headers=auth).json()
        assert extraction["fields"]
        assert all(field["evidence"]["id"] for field in extraction["fields"])
    approval = client.post(f"/api/v1/cases/{case_id}/approvals", headers=auth, json={
        "expected_version": case["version"], "decision": "APPROVED", "reason": "虚构材料回归验收",
    })
    assert approval.status_code == (409 if scenario["expected"] else 201)
