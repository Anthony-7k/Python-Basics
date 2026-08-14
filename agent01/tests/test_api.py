from fastapi.testclient import TestClient

from app.main import app

from unittest.mock import patch

client = TestClient(app)


def test_health():
    response = client.get("/health")

    assert response.status_code == 200

    assert response.json()["status"] == "ok"


def test_ready():
    response = client.get("/ready")

    assert response.status_code == 200

    assert response.json()["status"] == "ready"


def test_chat_validation_error():
    response = client.post(
        "/api/v1/chat",
        json={
            "question": ""
        },
    )

    assert response.status_code == 422


def test_chat_success():
    fake_response = {
        "answer": "测试答案",
        "sources": [],
        "used_chunk_ids": [],
        "request_id": "test-request-id",
    }

    with patch(
        "app.api.routes.chat.answer_question",
        return_value=fake_response,
    ):
        response = client.post(
            "/api/v1/chat",
            json={
                "question": "测试问题"
            },
        )

    assert response.status_code == 200

    data = response.json()

    assert data["answer"] == "测试答案"
    assert "request_id" in data