from __future__ import annotations

import httpx
import pytest

from app.tools.base import ToolExecutionFailure
from app.tools.knowledge import (
    Agent01HttpKnowledgeBackend,
    FallbackKnowledgeBackend,
    SampleKnowledgeBackend,
)


@pytest.mark.asyncio
async def test_agent01_adapter_preserves_sources_and_auth(monkeypatch):
    real_client = httpx.AsyncClient

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/chat"
        assert request.headers["Authorization"] == "Bearer demo-token"
        assert request.headers["X-Request-ID"] == "req-1"
        return httpx.Response(
            200,
            json={
                "answer": "制度答案",
                "sources": [
                    {
                        "source_id": "S1",
                        "chunk_id": "chunk-1",
                        "file_name": "handbook.pdf",
                        "page": 3,
                        "content": "员工每年享有年假。",
                        "score": 0.94,
                    }
                ],
                "request_id": "rag-1",
                "latency_ms": 12.5,
            },
        )

    transport = httpx.MockTransport(handler)

    def client_factory(*, timeout):
        return real_client(transport=transport, timeout=timeout)

    monkeypatch.setattr("app.tools.knowledge.httpx.AsyncClient", client_factory)
    backend = Agent01HttpKnowledgeBackend(
        "http://agent01", "demo-token", "kb-1", timeout_seconds=1
    )
    result = await backend.search(
        "年假", knowledge_base_id=None, request_id="req-1", top_k=5
    )
    assert result["backend"] == "agent01"
    assert result["sources"][0]["untrusted"] is True
    assert result["sources"][0]["title"] == "handbook.pdf"
    assert result["sources"][0]["locator"] == "handbook.pdf / chunk-1 / page:3"
    assert result["sources"][0]["score"] == 0.94
    assert result["request_id"] == "rag-1"
    assert result["knowledge_base_id"] == "kb-1"


class FailingBackend:
    async def search(self, query, **kwargs):
        raise ToolExecutionFailure("knowledge_unavailable", "down", retryable=True)


@pytest.mark.asyncio
async def test_knowledge_backend_can_fall_back_to_sample():
    backend = FallbackKnowledgeBackend(FailingBackend(), SampleKnowledgeBackend())
    result = await backend.search(
        "年假制度", knowledge_base_id=None, request_id="req-2", top_k=5
    )
    assert result["fallback_used"] is True
    assert result["backend"] == "sample"


@pytest.mark.parametrize(
    ("status_code", "error_type", "retryable"),
    [
        (401, "knowledge_unauthorized", False),
        (403, "knowledge_forbidden", False),
        (429, "knowledge_backend_unavailable", True),
        (503, "knowledge_backend_unavailable", True),
    ],
)
@pytest.mark.asyncio
async def test_agent01_errors_are_stable(
    monkeypatch, status_code, error_type, retryable
):
    real_client = httpx.AsyncClient

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"detail": "not exposed"})

    transport = httpx.MockTransport(handler)

    def client_factory(*, timeout):
        return real_client(transport=transport, timeout=timeout)

    monkeypatch.setattr("app.tools.knowledge.httpx.AsyncClient", client_factory)
    backend = Agent01HttpKnowledgeBackend("http://agent01", "token", "kb-1")
    with pytest.raises(ToolExecutionFailure) as caught:
        await backend.search(
            "制度", knowledge_base_id=None, request_id="req-error", top_k=5
        )
    assert caught.value.error_type == error_type
    assert caught.value.retryable is retryable


@pytest.mark.asyncio
async def test_agent01_rejects_invalid_response(monkeypatch):
    real_client = httpx.AsyncClient

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"answer": "missing contract fields"})

    transport = httpx.MockTransport(handler)

    def client_factory(*, timeout):
        return real_client(transport=transport, timeout=timeout)

    monkeypatch.setattr("app.tools.knowledge.httpx.AsyncClient", client_factory)
    backend = Agent01HttpKnowledgeBackend("http://agent01", "token", "kb-1")
    with pytest.raises(ToolExecutionFailure) as caught:
        await backend.search(
            "制度", knowledge_base_id=None, request_id="req-invalid", top_k=5
        )
    assert caught.value.error_type == "knowledge_invalid_response"
    assert caught.value.retryable is False
