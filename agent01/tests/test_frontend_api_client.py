import json

import httpx
import pytest

from frontend.api_client import APIClient, APIClientError


def make_client(handler):
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(
        base_url="http://testserver",
        transport=transport,
    )
    return APIClient("http://testserver", client=http_client), http_client


def test_list_knowledge_bases_parses_items():
    def handler(request):
        assert request.url.path == "/api/v1/knowledge-bases"
        return httpx.Response(
            200,
            json={"items": [{"id": "kb-1", "name": "Handbook"}]},
        )

    client, http_client = make_client(handler)
    try:
        assert client.list_knowledge_bases() == [
            {"id": "kb-1", "name": "Handbook"}
        ]
    finally:
        http_client.close()


def test_upload_document_returns_task_and_scopes_knowledge_base():
    def handler(request):
        assert request.url.params["knowledge_base_id"] == "kb-1"
        assert b"policy.txt" in request.content
        return httpx.Response(
            202,
            json={
                "document_id": "doc-1",
                "task_id": "task-1",
                "status": "pending",
            },
        )

    client, http_client = make_client(handler)
    try:
        result = client.upload_document(
            "kb-1",
            file_name="policy.txt",
            content=b"travel policy",
            content_type="text/plain",
        )
    finally:
        http_client.close()

    assert result["task_id"] == "task-1"
    assert result["status"] == "pending"


@pytest.mark.parametrize(
    "status,error",
    [
        ("pending", None),
        ("running", None),
        ("succeeded", None),
        ("failed", "embedding failed"),
    ],
)
def test_ingestion_statuses_are_returned_without_loss(status, error):
    client, http_client = make_client(
        lambda request: httpx.Response(
            200,
            json={
                "task_id": "task-1",
                "document_id": "doc-1",
                "status": status,
                "error": error,
            },
        )
    )
    try:
        result = client.get_ingestion_status("task-1")
    finally:
        http_client.close()

    assert result["status"] == status
    assert result["error"] == error


def test_chat_reuses_conversation_id_and_keeps_sources():
    captured_payloads = []

    def handler(request):
        captured_payloads.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "conversation_id": "conv-1",
                "answer": "限额为 500 元。",
                "sources": [
                    {
                        "source_id": "S1",
                        "chunk_id": "chunk-1",
                        "file_name": "policy.pdf",
                        "page": 2,
                        "content": "住宿标准为每日 500 元。",
                    }
                ],
                "used_chunk_ids": ["chunk-1"],
                "request_id": "request-1",
            },
        )

    client, http_client = make_client(handler)
    try:
        first = client.chat("kb-1", "住宿上限是多少？")
        second = client.chat(
            "kb-1",
            "那餐补呢？",
            conversation_id=first["conversation_id"],
        )
    finally:
        http_client.close()

    assert "conversation_id" not in captured_payloads[0]
    assert captured_payloads[1]["conversation_id"] == "conv-1"
    assert second["sources"][0]["content"] == "住宿标准为每日 500 元。"


def test_timeout_becomes_actionable_error():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    client, http_client = make_client(handler)
    try:
        with pytest.raises(APIClientError, match="请求超时"):
            client.list_knowledge_bases()
    finally:
        http_client.close()


def test_connection_failure_becomes_actionable_error():
    def handler(request):
        raise httpx.ConnectError("offline", request=request)

    client, http_client = make_client(handler)
    try:
        with pytest.raises(APIClientError, match="无法连接 FastAPI"):
            client.list_knowledge_bases()
    finally:
        http_client.close()


def test_http_error_includes_backend_detail_and_next_step():
    client, http_client = make_client(
        lambda request: httpx.Response(
            404,
            json={"detail": "Document not found"},
        )
    )
    try:
        with pytest.raises(APIClientError) as error:
            client.delete_document("kb-1", "doc-missing")
    finally:
        http_client.close()

    assert error.value.status_code == 404
    assert "Document not found" in error.value.user_message
    assert "刷新知识库或文档列表" in error.value.user_message


def test_validation_error_is_readable():
    client, http_client = make_client(
        lambda request: httpx.Response(
            422,
            json={
                "detail": [
                    {
                        "loc": ["body", "question"],
                        "msg": "String should have at least 1 character",
                    }
                ]
            },
        )
    )
    try:
        with pytest.raises(APIClientError) as error:
            client.chat("kb-1", "")
    finally:
        http_client.close()

    assert "body.question" in error.value.user_message
    assert "检查必填项" in error.value.user_message


def test_malformed_list_response_is_rejected():
    client, http_client = make_client(
        lambda request: httpx.Response(200, json={"items": "not-a-list"})
    )
    try:
        with pytest.raises(APIClientError, match="知识库列表响应格式异常"):
            client.list_knowledge_bases()
    finally:
        http_client.close()
