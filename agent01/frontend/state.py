"""Pure session-state helpers for the Streamlit frontend."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any


def initialize_state(state: MutableMapping[str, Any]) -> None:
    state.setdefault("selected_knowledge_base_id", None)
    state.setdefault("conversation_id", None)
    state.setdefault("messages", [])
    state.setdefault("chat_sessions", {})
    state.setdefault("ingestion_tasks", {})
    state.setdefault("last_chat_meta", None)


def switch_knowledge_base(
    state: MutableMapping[str, Any],
    knowledge_base_id: str | None,
) -> bool:
    """Switch knowledge bases without ever reusing another base's session."""

    initialize_state(state)
    current_id = state.get("selected_knowledge_base_id")
    if current_id == knowledge_base_id:
        return False

    _save_current_chat(state)
    state["selected_knowledge_base_id"] = knowledge_base_id

    saved = state["chat_sessions"].get(knowledge_base_id, {})
    state["conversation_id"] = saved.get("conversation_id")
    state["messages"] = list(saved.get("messages", []))
    state["last_chat_meta"] = saved.get("last_chat_meta")
    return True


def append_message(
    state: MutableMapping[str, Any],
    *,
    role: str,
    content: str,
    sources: list[dict[str, Any]] | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    initialize_state(state)
    message: dict[str, Any] = {
        "role": role,
        "content": content,
    }
    if sources is not None:
        message["sources"] = sources
    if meta is not None:
        message["meta"] = meta
        state["last_chat_meta"] = meta

    state["messages"].append(message)
    _save_current_chat(state)


def set_conversation_id(
    state: MutableMapping[str, Any],
    conversation_id: str | None,
) -> None:
    initialize_state(state)
    state["conversation_id"] = conversation_id
    _save_current_chat(state)


def clear_current_chat(state: MutableMapping[str, Any]) -> None:
    initialize_state(state)
    knowledge_base_id = state.get("selected_knowledge_base_id")
    state["conversation_id"] = None
    state["messages"] = []
    state["last_chat_meta"] = None
    if knowledge_base_id is not None:
        state["chat_sessions"][knowledge_base_id] = {
            "conversation_id": None,
            "messages": [],
            "last_chat_meta": None,
        }


def set_ingestion_task(
    state: MutableMapping[str, Any],
    knowledge_base_id: str,
    task: Mapping[str, Any] | None,
) -> None:
    initialize_state(state)
    if task is None:
        state["ingestion_tasks"].pop(knowledge_base_id, None)
    else:
        state["ingestion_tasks"][knowledge_base_id] = dict(task)


def get_ingestion_task(
    state: MutableMapping[str, Any],
    knowledge_base_id: str,
) -> dict[str, Any] | None:
    initialize_state(state)
    task = state["ingestion_tasks"].get(knowledge_base_id)
    return dict(task) if isinstance(task, Mapping) else None


def normalize_source(source: Mapping[str, Any] | None) -> dict[str, Any]:
    source = source or {}
    page = source.get("page")
    has_page = isinstance(page, int) and page > 0
    raw_file_name = str(source.get("file_name") or "")
    display_file_name = (
        raw_file_name.replace("\\", "/").rstrip("/").split("/")[-1]
        if raw_file_name
        else "未命名文档"
    )
    return {
        "source_id": str(source.get("source_id") or "未知来源"),
        "file_name": display_file_name,
        "page": page if has_page else None,
        "page_label": f"第 {page} 页" if has_page else "无页码",
        "content": str(source.get("content") or "暂无证据片段"),
        "chunk_id": str(source.get("chunk_id") or ""),
    }


def ingestion_status_copy(
    status: str | None,
    error: str | None = None,
) -> tuple[str, str]:
    normalized = (status or "unknown").lower()
    if normalized == "pending":
        return "等待处理", "任务已提交；稍后点击“刷新入库状态”。"
    if normalized == "running":
        return "正在入库", "正在解析、切分并建立索引；请稍后刷新。"
    if normalized == "succeeded":
        return "入库成功", "文档已可用于问答。"
    if normalized == "failed":
        detail = error or "后端未返回失败原因"
        return "入库失败", f"{detail}。请检查 FastAPI 日志后重新上传或重建索引。"
    return "状态未知", "请刷新状态；若仍未知，请检查 FastAPI 日志。"


def _save_current_chat(state: MutableMapping[str, Any]) -> None:
    knowledge_base_id = state.get("selected_knowledge_base_id")
    if knowledge_base_id is None:
        return
    state["chat_sessions"][knowledge_base_id] = {
        "conversation_id": state.get("conversation_id"),
        "messages": list(state.get("messages", [])),
        "last_chat_meta": state.get("last_chat_meta"),
    }
