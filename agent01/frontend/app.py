"""Streamlit console for the enterprise knowledge base agent."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import streamlit as st

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from frontend.api_client import (
    APIClient,
    APIClientError,
    DEFAULT_API_BASE_URL,
)
from frontend.components import (
    render_chat_meta,
    render_sources,
    status_badge,
)
from frontend.state import (
    append_message,
    clear_current_chat,
    get_ingestion_task,
    ingestion_status_copy,
    initialize_state,
    restore_chat,
    set_conversation_id,
    set_ingestion_task,
    switch_knowledge_base,
)


st.set_page_config(
    page_title="企业知识库 Agent",
    page_icon="📚",
    layout="wide",
)


def main() -> None:
    initialize_state(st.session_state)
    st.session_state.setdefault(
        "api_base_url",
        os.getenv("API_BASE_URL", DEFAULT_API_BASE_URL),
    )

    st.title("企业知识库 Agent")
    st.caption("通过 FastAPI 管理文档、进行多轮问答，并查看可追溯证据。")

    client = _build_client()
    if client is None:
        return

    knowledge_bases = _load_knowledge_bases(client)
    if knowledge_bases is None:
        return

    _render_create_knowledge_base(client)
    selected_id = _render_knowledge_base_selector(knowledge_bases)
    if selected_id is None:
        st.info("还没有知识库。请先在左侧创建一个，再上传文档。")
        return

    _render_uploader(client, selected_id)

    documents = _load_documents(client, selected_id)
    if documents is None:
        documents = []

    _restore_conversation_from_query(
        client,
        selected_id,
    )

    chat_tab, documents_tab = st.tabs(["💬 知识问答", "📄 文档管理"])
    with chat_tab:
        _render_chat(client, selected_id, documents)
    with documents_tab:
        _render_documents(client, selected_id, documents)


def _build_client() -> APIClient | None:
    with st.sidebar:
        st.header("连接与知识库")
        st.text_input(
            "FastAPI 地址",
            key="api_base_url",
            help="也可通过环境变量 API_BASE_URL 设置。",
        )

    try:
        client = APIClient(st.session_state.api_base_url)
    except ValueError as exc:
        st.sidebar.error(str(exc))
        st.error("API 地址无效，请在左侧输入完整的 http:// 或 https:// 地址。")
        return None

    if st.sidebar.button("检查 API 连接", use_container_width=True):
        try:
            client.health()
        except APIClientError as exc:
            st.sidebar.error(exc.user_message)
        else:
            st.sidebar.success("FastAPI 连接正常")
    return client


def _load_knowledge_bases(
    client: APIClient,
) -> list[dict[str, Any]] | None:
    try:
        return client.list_knowledge_bases()
    except APIClientError as exc:
        st.sidebar.error(exc.user_message)
        st.error(
            "暂时无法加载知识库。请按左侧提示启动或检查 FastAPI，"
            "确认后刷新页面。"
        )
        return None


def _render_create_knowledge_base(client: APIClient) -> None:
    with st.sidebar.expander("新建知识库", expanded=False):
        with st.form("create_knowledge_base", clear_on_submit=True):
            name = st.text_input("名称", max_chars=255)
            description = st.text_area("描述（可选）", max_chars=2000)
            submitted = st.form_submit_button(
                "创建",
                use_container_width=True,
            )
        if submitted:
            if not name.strip():
                st.warning("请输入知识库名称。")
            else:
                try:
                    created = client.create_knowledge_base(name, description)
                except APIClientError as exc:
                    st.error(exc.user_message)
                else:
                    st.session_state.selected_knowledge_base_id = created.get("id")
                    st.query_params["knowledge_base_id"] = str(
                        created.get("id")
                    )
                    st.query_params.pop(
                        "conversation_id",
                        None,
                    )
                    st.success("知识库已创建")
                    st.rerun()


def _render_knowledge_base_selector(
    knowledge_bases: list[dict[str, Any]],
) -> str | None:
    if not knowledge_bases:
        switch_knowledge_base(st.session_state, None)
        return None

    by_id = {
        str(item["id"]): item
        for item in knowledge_bases
        if item.get("id") is not None
    }
    if not by_id:
        st.sidebar.error("知识库列表缺少 id，请检查 API 版本。")
        return None

    ids = list(by_id)
    current_id = st.session_state.selected_knowledge_base_id
    if current_id not in by_id:
        requested_id = str(
            st.query_params.get(
                "knowledge_base_id"
            )
            or ""
        )
        current_id = (
            requested_id
            if requested_id in by_id
            else ids[0]
        )

    selected_id = st.sidebar.selectbox(
        "当前知识库",
        options=ids,
        index=ids.index(current_id),
        format_func=lambda item_id: str(by_id[item_id].get("name") or item_id),
    )
    switch_knowledge_base(st.session_state, selected_id)
    if (
        st.query_params.get("knowledge_base_id")
        != selected_id
    ):
        st.query_params["knowledge_base_id"] = selected_id
        st.query_params.pop(
            "conversation_id",
            None,
        )

    selected = by_id[selected_id]
    description = selected.get("description") or "暂无描述"
    st.sidebar.caption(
        f"版本 {selected.get('version', '-')} · {description}"
    )
    return selected_id


def _restore_conversation_from_query(
    client: APIClient,
    knowledge_base_id: str,
) -> None:
    conversation_id = str(
        st.query_params.get("conversation_id")
        or ""
    ).strip()
    if not conversation_id:
        return
    if (
        st.session_state.conversation_id
        == conversation_id
        and st.session_state.messages
    ):
        return

    try:
        conversation = client.get_conversation(
            conversation_id
        )
    except APIClientError as exc:
        st.warning(
            "无法恢复 URL 中的会话："
            f"{exc.user_message}"
        )
        st.query_params.pop(
            "conversation_id",
            None,
        )
        return

    if (
        str(conversation.get("knowledge_base_id"))
        != knowledge_base_id
    ):
        st.warning(
            "该会话不属于当前知识库，已停止恢复。"
        )
        st.query_params.pop(
            "conversation_id",
            None,
        )
        return

    raw_messages = conversation.get("messages")
    messages = (
        [
            dict(item)
            for item in raw_messages
            if isinstance(item, Mapping)
        ]
        if isinstance(raw_messages, list)
        else []
    )
    restore_chat(
        st.session_state,
        knowledge_base_id=knowledge_base_id,
        conversation_id=conversation_id,
        messages=messages,
    )


def _render_uploader(client: APIClient, knowledge_base_id: str) -> None:
    st.sidebar.divider()
    st.sidebar.subheader("上传文档")
    uploaded_file = st.sidebar.file_uploader(
        "支持 PDF、DOCX、TXT",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=False,
    )
    if st.sidebar.button(
        "上传并开始入库",
        disabled=uploaded_file is None,
        use_container_width=True,
    ):
        assert uploaded_file is not None
        try:
            result = client.upload_document(
                knowledge_base_id,
                file_name=uploaded_file.name,
                content=uploaded_file.getvalue(),
                content_type=uploaded_file.type,
            )
        except APIClientError as exc:
            st.sidebar.error(exc.user_message)
        else:
            set_ingestion_task(
                st.session_state,
                knowledge_base_id,
                result,
            )
            st.sidebar.success("上传成功，已提交入库任务")
            st.rerun()

    _render_ingestion_task(client, knowledge_base_id)


def _render_ingestion_task(client: APIClient, knowledge_base_id: str) -> None:
    task = get_ingestion_task(st.session_state, knowledge_base_id)
    if not task:
        return

    status = str(task.get("status") or "unknown")
    label, guidance = ingestion_status_copy(status, task.get("error"))
    st.sidebar.markdown(f"**最近任务：{label}**")
    st.sidebar.caption(guidance)

    if status not in {"succeeded", "failed"}:
        if st.sidebar.button(
            "刷新入库状态",
            use_container_width=True,
        ):
            try:
                refreshed = client.get_ingestion_status(str(task["task_id"]))
            except APIClientError as exc:
                st.sidebar.error(exc.user_message)
            else:
                set_ingestion_task(
                    st.session_state,
                    knowledge_base_id,
                    refreshed,
                )
                st.rerun()
    elif st.sidebar.button("关闭任务提示", use_container_width=True):
        set_ingestion_task(st.session_state, knowledge_base_id, None)
        st.rerun()


def _load_documents(
    client: APIClient,
    knowledge_base_id: str,
) -> list[dict[str, Any]] | None:
    try:
        return client.list_documents(knowledge_base_id)
    except APIClientError as exc:
        st.error(exc.user_message)
        st.info("请刷新页面；若仍失败，请确认该知识库仍存在并查看 FastAPI 日志。")
        return None


def _render_chat(
    client: APIClient,
    knowledge_base_id: str,
    documents: list[dict[str, Any]],
) -> None:
    header, action = st.columns([4, 1])
    with header:
        st.subheader("与当前知识库对话")
        conversation_id = st.session_state.conversation_id
        if conversation_id:
            st.caption(f"当前会话：{conversation_id}")
        else:
            st.caption("发送第一条消息后会自动创建并保存会话。")
    with action:
        if st.button("清空当前会话", use_container_width=True):
            clear_current_chat(st.session_state)
            st.query_params.pop(
                "conversation_id",
                None,
            )
            st.rerun()

    if not documents:
        st.info("当前知识库还没有可见文档。请先在左侧上传并等待入库成功。")

    for message in st.session_state.messages:
        role = "assistant" if message.get("role") == "assistant" else "user"
        with st.chat_message(role):
            st.markdown(str(message.get("content") or ""))
            if role == "assistant":
                render_sources(message.get("sources"))
                render_chat_meta(message.get("meta"))

    question = st.chat_input(
        "输入关于当前知识库的问题",
        disabled=not documents,
    )
    if not question or not question.strip():
        return

    question = question.strip()
    append_message(
        st.session_state,
        role="user",
        content=question,
    )
    with st.chat_message("user"):
        st.markdown(question)

    try:
        with st.spinner("正在检索证据并生成回答……"):
            response = client.chat(
                knowledge_base_id,
                question,
                conversation_id=st.session_state.conversation_id,
            )
    except APIClientError as exc:
        st.error(exc.user_message)
        st.info("问题已保留在当前页面；确认后端恢复后，可重新发送。")
        return

    conversation_id = response.get("conversation_id")
    if conversation_id:
        set_conversation_id(st.session_state, str(conversation_id))
        st.query_params["knowledge_base_id"] = (
            knowledge_base_id
        )
        st.query_params["conversation_id"] = str(
            conversation_id
        )

    raw_sources = response.get("sources")
    sources = (
        [dict(item) for item in raw_sources if isinstance(item, Mapping)]
        if isinstance(raw_sources, list)
        else []
    )
    meta = {
        "cache_hit": bool(response.get("cache_hit")),
        "retrieval_ms": response.get("retrieval_ms", 0),
        "latency_ms": response.get("latency_ms", 0),
        "request_id": response.get("request_id"),
    }
    append_message(
        st.session_state,
        role="assistant",
        content=str(response.get("answer") or "后端没有返回回答内容。"),
        sources=sources,
        meta=meta,
    )
    st.rerun()


def _render_documents(
    client: APIClient,
    knowledge_base_id: str,
    documents: list[dict[str, Any]],
) -> None:
    title, refresh = st.columns([4, 1])
    title.subheader("文档列表")
    refresh.button("刷新文档列表", use_container_width=True)
    st.caption("页面每次重载都会从 FastAPI 重新读取列表，不依赖本地前端缓存。")

    if not documents:
        st.info("当前知识库没有文档。请使用左侧上传区域添加 PDF、DOCX 或 TXT。")
        return

    for document in documents:
        document_id = str(document.get("id") or "")
        file_name = str(document.get("file_name") or "未命名文档")
        with st.container(border=True):
            info, actions = st.columns([3, 2])
            with info:
                st.markdown(f"**{file_name}**")
                st.write(status_badge(str(document.get("status") or "unknown")))
                st.caption(f"Document ID: {document_id}")
            with actions:
                confirm_reindex = st.checkbox(
                    "确认重建索引",
                    key=f"confirm_reindex_{document_id}",
                )
                if st.button(
                    "重建索引",
                    key=f"reindex_{document_id}",
                    disabled=not confirm_reindex,
                    use_container_width=True,
                ):
                    _reindex_document(client, knowledge_base_id, document_id)

                confirm_delete = st.checkbox(
                    "确认删除文档",
                    key=f"confirm_delete_{document_id}",
                )
                if st.button(
                    "删除",
                    key=f"delete_{document_id}",
                    disabled=not confirm_delete,
                    type="secondary",
                    use_container_width=True,
                ):
                    _delete_document(client, knowledge_base_id, document_id)


def _reindex_document(
    client: APIClient,
    knowledge_base_id: str,
    document_id: str,
) -> None:
    try:
        task = client.reindex_document(knowledge_base_id, document_id)
    except APIClientError as exc:
        st.error(exc.user_message)
        return
    set_ingestion_task(st.session_state, knowledge_base_id, task)
    st.success("重建任务已提交，可在左侧刷新状态。")
    st.rerun()


def _delete_document(
    client: APIClient,
    knowledge_base_id: str,
    document_id: str,
) -> None:
    try:
        client.delete_document(knowledge_base_id, document_id)
    except APIClientError as exc:
        st.error(exc.user_message)
        return
    st.success("文档已删除")
    st.rerun()


if __name__ == "__main__":
    main()
