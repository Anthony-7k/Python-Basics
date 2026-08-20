"""Reusable visual components for the Streamlit page."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import streamlit as st

from frontend.state import normalize_source


def render_sources(sources: Sequence[Mapping[str, Any]] | None) -> None:
    if not sources:
        st.caption("本次回答没有返回可展示的来源。")
        return

    st.markdown("**参考来源**")
    for index, raw_source in enumerate(sources, start=1):
        source = normalize_source(raw_source)
        label = (
            f"[{source['source_id']}] {source['file_name']} · "
            f"{source['page_label']}"
        )
        with st.expander(label, expanded=False):
            st.write(source["content"])
            if source["chunk_id"]:
                st.caption(f"Chunk: {source['chunk_id']}")
            st.caption(f"来源序号：{index}")


def render_chat_meta(meta: Mapping[str, Any] | None) -> None:
    if not meta:
        return

    cache_label = "命中" if meta.get("cache_hit") else "未命中"
    with st.expander("本次请求状态", expanded=False):
        columns = st.columns(3)
        columns[0].metric("检索缓存", cache_label)
        columns[1].metric(
            "检索耗时",
            f"{float(meta.get('retrieval_ms') or 0):.2f} ms",
        )
        columns[2].metric(
            "总耗时",
            f"{float(meta.get('latency_ms') or 0):.2f} ms",
        )
        request_id = meta.get("request_id")
        if request_id:
            st.caption(f"Request ID: {request_id}")


def status_badge(status: str | None) -> str:
    labels = {
        "pending": "🟡 等待处理",
        "running": "🔵 正在处理",
        "succeeded": "🟢 可用",
        "failed": "🔴 失败",
        "deleted": "⚪ 已删除",
        "processing": "🔵 正在处理",
        "indexed": "🟢 可用",
        "ready": "🟢 可用",
    }
    normalized = (status or "unknown").lower()
    return labels.get(normalized, f"⚪ {status or '未知'}")
