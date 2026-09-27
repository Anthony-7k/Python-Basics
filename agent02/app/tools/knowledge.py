from __future__ import annotations

from time import perf_counter
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.domain import KnowledgeSource
from app.tools.base import BaseTool, ToolContext, ToolExecutionFailure


class KnowledgeQuery(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


class KnowledgeBackend(Protocol):
    async def search(
        self,
        query: str,
        *,
        knowledge_base_id: str | None,
        request_id: str,
        top_k: int,
    ) -> dict[str, Any]: ...


class Agent01Source(BaseModel):
    source_id: str
    chunk_id: str
    file_name: str | None = None
    page: int | None = None
    content: str
    score: float | None = Field(default=None, ge=0, le=1)
    url: str | None = None


class Agent01Response(BaseModel):
    answer: str
    sources: list[Agent01Source]
    request_id: str
    latency_ms: float = Field(ge=0)


class SampleKnowledgeBackend:
    """Deterministic fallback used by local demos and automated tests."""

    async def search(
        self,
        query: str,
        *,
        knowledge_base_id: str | None,
        request_id: str,
        top_k: int,
    ) -> dict[str, Any]:
        if "差旅" in query or "报销" in query or "出差" in query:
            answer = (
                "上海差旅标准：住宿每日 500 元、餐补每日 150 元、"
                "市内交通每日 100 元，单日合计上限 750 元。"
            )
            facts = {
                "daily_lodging_limit": 500,
                "daily_meal_limit": 150,
                "daily_transport_limit": 100,
                "daily_total_limit": 750,
            }
            source = "sample://company-policy/shanghai-travel"
            title = "上海差旅标准"
        elif "年假" in query or "休假" in query:
            answer = (
                "示例制度：员工每年享有 10 天年假；休假应提前申请，"
                "连续三天及以上需直属负责人审批。"
            )
            facts = {"annual_leave_days": 10, "approval_threshold_days": 3}
            source = "sample://employee-handbook/annual-leave"
            title = "员工手册年假制度"
        else:
            answer = "示例知识库中没有足够的信息回答该问题。"
            facts = {}
            source = "sample://knowledge-base/unanswerable"
            title = "样例知识库"
        return {
            "answer": answer,
            "facts": facts,
            "sources": [
                {
                    **KnowledgeSource(
                        source_id="S1",
                        title=title,
                        source_type="sample",
                        locator=source,
                        content=answer,
                    ).model_dump(mode="json"),
                }
            ],
            "backend": "sample",
            "request_id": request_id,
        }


class Agent01HttpKnowledgeBackend:
    def __init__(
        self,
        base_url: str,
        bearer_token: str,
        default_knowledge_base_id: str,
        *,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.bearer_token = bearer_token
        self.default_knowledge_base_id = default_knowledge_base_id
        self.timeout_seconds = timeout_seconds

    async def search(
        self,
        query: str,
        *,
        knowledge_base_id: str | None,
        request_id: str,
        top_k: int,
    ) -> dict[str, Any]:
        payload = {
            "question": query,
            "knowledge_base_id": knowledge_base_id or self.default_knowledge_base_id,
        }
        started = perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/chat",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.bearer_token}",
                        "X-Request-ID": request_id,
                    },
                )
                if response.status_code == 401:
                    raise ToolExecutionFailure(
                        "knowledge_unauthorized",
                        "agent01 rejected the configured credential",
                        retryable=False,
                    )
                if response.status_code == 403:
                    raise ToolExecutionFailure(
                        "knowledge_forbidden",
                        "agent01 denied access to the knowledge base",
                        retryable=False,
                    )
                if response.status_code == 429:
                    raise ToolExecutionFailure(
                        "knowledge_backend_unavailable",
                        "agent01 rate limit was reached",
                        retryable=True,
                    )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ToolExecutionFailure(
                "knowledge_timeout",
                "agent01 knowledge service timed out",
                retryable=True,
            ) from exc
        except ToolExecutionFailure:
            raise
        except httpx.HTTPError as exc:
            raise ToolExecutionFailure(
                "knowledge_backend_unavailable",
                "agent01 knowledge service is unavailable",
                retryable=True,
            ) from exc
        try:
            data = Agent01Response.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise ToolExecutionFailure(
                "knowledge_invalid_response",
                "agent01 returned an invalid response",
                retryable=False,
            ) from exc

        sources = [self._normalize_source(item) for item in data.sources[:top_k]]
        resolved_kb = knowledge_base_id or self.default_knowledge_base_id
        return {
            "answer": data.answer,
            "facts": {},
            "sources": sources,
            "backend": "agent01",
            "request_id": data.request_id,
            "knowledge_base_id": resolved_kb,
            "latency_ms": data.latency_ms,
            "adapter_latency_ms": round((perf_counter() - started) * 1000, 3),
        }

    @staticmethod
    def _normalize_source(item: Agent01Source) -> dict[str, Any]:
        locator_parts = [part for part in (item.file_name, item.chunk_id) if part]
        if item.page is not None:
            locator_parts.append(f"page:{item.page}")
        return KnowledgeSource(
            source_id=item.source_id,
            title=item.file_name or item.chunk_id,
            source_type="document",
            locator=" / ".join(locator_parts),
            score=item.score,
            url=item.url,
            content=item.content,
        ).model_dump(mode="json")


class FallbackKnowledgeBackend:
    def __init__(self, primary: KnowledgeBackend, fallback: KnowledgeBackend) -> None:
        self.primary = primary
        self.fallback = fallback

    async def search(self, query: str, **kwargs: Any) -> dict[str, Any]:
        try:
            return await self.primary.search(query, **kwargs)
        except ToolExecutionFailure:
            result = await self.fallback.search(query, **kwargs)
            result["fallback_used"] = True
            return result


class KnowledgeTool(BaseTool[KnowledgeQuery]):
    name = "knowledge"
    description = "Search the authorized enterprise knowledge base and return sources"
    args_model = KnowledgeQuery

    def __init__(self, backend: KnowledgeBackend) -> None:
        self.backend = backend

    async def execute(
        self, arguments: KnowledgeQuery, context: ToolContext
    ) -> dict[str, Any]:
        return await self.backend.search(
            arguments.query,
            knowledge_base_id=context.knowledge_base_id,
            request_id=context.request_id,
            top_k=arguments.top_k,
        )
