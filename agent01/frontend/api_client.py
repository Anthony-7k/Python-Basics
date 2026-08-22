"""HTTP-only client used by the Streamlit frontend."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx


DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_API_TIMEOUT_SECONDS = 60.0


class APIClientError(RuntimeError):
    """A backend or network error that is safe to show in the UI."""

    def __init__(
        self,
        user_message: str,
        *,
        status_code: int | None = None,
        detail: str | None = None,
    ) -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.status_code = status_code
        self.detail = detail


class APIClient:
    """Small typed-by-convention wrapper around the FastAPI endpoints."""

    def __init__(
        self,
        base_url: str = DEFAULT_API_BASE_URL,
        *,
        timeout_seconds: float = DEFAULT_API_TIMEOUT_SECONDS,
        client: httpx.Client | None = None,
    ) -> None:
        normalized_url = base_url.strip().rstrip("/")
        if not normalized_url.startswith(("http://", "https://")):
            raise ValueError("API 地址必须以 http:// 或 https:// 开头")

        self.base_url = normalized_url
        self.timeout_seconds = timeout_seconds
        self._client = client

    def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> Any:
        try:
            if self._client is not None:
                response = self._client.request(
                    method,
                    path,
                    **kwargs,
                )
            else:
                with httpx.Client(
                    base_url=self.base_url,
                    timeout=self.timeout_seconds,
                ) as client:
                    response = client.request(
                        method,
                        path,
                        **kwargs,
                    )
        except httpx.TimeoutException as exc:
            raise APIClientError(
                "请求超时。请确认 FastAPI 和依赖服务正常运行，然后重试。"
            ) from exc
        except httpx.ConnectError as exc:
            raise APIClientError(
                "无法连接 FastAPI。请先运行 `uv run uvicorn app.main:app "
                "--host 127.0.0.1 --port 8000`，再重试。"
            ) from exc
        except httpx.RequestError as exc:
            raise APIClientError(
                "网络请求失败。请检查 API 地址、网络连接和后端日志后重试。"
            ) from exc

        if response.is_error:
            detail = _extract_error_detail(response)
            hint = _status_hint(response.status_code)
            raise APIClientError(
                f"API 返回 {response.status_code}：{detail}。{hint}",
                status_code=response.status_code,
                detail=detail,
            )

        if response.status_code == 204:
            return None

        try:
            return response.json()
        except ValueError as exc:
            raise APIClientError(
                "API 返回了无法解析的数据。请检查后端日志与接口版本。"
            ) from exc

    def health(self) -> dict[str, Any]:
        return _as_mapping(self._request("GET", "/health"), "健康检查")

    def list_knowledge_bases(self) -> list[dict[str, Any]]:
        payload = _as_mapping(
            self._request("GET", "/api/v1/knowledge-bases"),
            "知识库列表",
        )
        return _as_object_list(payload.get("items"), "知识库列表")

    def create_knowledge_base(
        self,
        name: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"name": name.strip()}
        if description and description.strip():
            payload["description"] = description.strip()
        return _as_mapping(
            self._request(
                "POST",
                "/api/v1/knowledge-bases",
                json=payload,
            ),
            "创建知识库",
        )

    def list_documents(
        self,
        knowledge_base_id: str,
        *,
        include_deleted: bool = False,
    ) -> list[dict[str, Any]]:
        payload = _as_mapping(
            self._request(
                "GET",
                f"/api/v1/knowledge-bases/{knowledge_base_id}/documents",
                params={"include_deleted": include_deleted},
            ),
            "文档列表",
        )
        return _as_object_list(payload.get("items"), "文档列表")

    def upload_document(
        self,
        knowledge_base_id: str,
        *,
        file_name: str,
        content: bytes,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        return _as_mapping(
            self._request(
                "POST",
                "/api/v1/documents",
                params={"knowledge_base_id": knowledge_base_id},
                files={
                    "file": (
                        file_name,
                        content,
                        content_type or "application/octet-stream",
                    )
                },
            ),
            "上传文档",
        )

    def get_ingestion_status(self, task_id: str) -> dict[str, Any]:
        return _as_mapping(
            self._request("GET", f"/api/v1/ingestion/{task_id}"),
            "入库任务",
        )

    def delete_document(
        self,
        knowledge_base_id: str,
        document_id: str,
    ) -> dict[str, Any]:
        return _as_mapping(
            self._request(
                "DELETE",
                f"/api/v1/documents/{document_id}",
                params={"knowledge_base_id": knowledge_base_id},
            ),
            "删除文档",
        )

    def reindex_document(
        self,
        knowledge_base_id: str,
        document_id: str,
    ) -> dict[str, Any]:
        return _as_mapping(
            self._request(
                "POST",
                "/api/v1/knowledge-bases/"
                f"{knowledge_base_id}/documents/{document_id}/reindex",
            ),
            "重建索引",
        )

    def chat(
        self,
        knowledge_base_id: str,
        question: str,
        *,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "knowledge_base_id": knowledge_base_id,
            "question": question,
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id

        return _as_mapping(
            self._request("POST", "/api/v1/chat", json=payload),
            "知识问答",
        )

    def get_conversation_messages(
        self,
        conversation_id: str,
    ) -> list[dict[str, Any]]:
        payload = _as_mapping(
            self._request(
                "GET",
                f"/api/v1/conversations/{conversation_id}/messages",
            ),
            "会话历史",
        )
        return _as_object_list(payload.get("messages"), "会话历史")


def _as_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise APIClientError(f"{label}响应格式异常，请检查 API 版本。")
    return dict(value)


def _as_object_list(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not all(
        isinstance(item, Mapping) for item in value
    ):
        raise APIClientError(f"{label}响应格式异常，请检查 API 版本。")
    return [dict(item) for item in value]


def _extract_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip() or "服务未提供错误详情"

    detail = payload.get("detail") if isinstance(payload, Mapping) else payload
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        messages = []
        for item in detail:
            if isinstance(item, Mapping):
                location = ".".join(str(part) for part in item.get("loc", []))
                message = str(item.get("msg", "参数无效"))
                messages.append(f"{location}: {message}" if location else message)
            else:
                messages.append(str(item))
        return "；".join(messages) or "请求参数无效"
    return str(detail) if detail is not None else "服务未提供错误详情"


def _status_hint(status_code: int) -> str:
    if status_code == 400:
        return "请检查文件格式、大小或输入内容后重试。"
    if status_code == 404:
        return "目标可能已被删除，请刷新知识库或文档列表。"
    if status_code == 409:
        return "当前资源状态不允许此操作，请刷新状态后重试。"
    if status_code == 422:
        return "请检查必填项和输入长度后重试。"
    if status_code >= 500:
        return "请查看 FastAPI 日志并确认 MySQL、Redis 与模型服务状态。"
    return "请刷新页面后重试；若仍失败，请查看 FastAPI 日志。"
