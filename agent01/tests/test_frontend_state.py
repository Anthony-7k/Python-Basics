import pytest

from frontend.state import (
    append_message,
    clear_current_chat,
    get_ingestion_task,
    ingestion_status_copy,
    initialize_state,
    normalize_source,
    set_conversation_id,
    set_ingestion_task,
    switch_knowledge_base,
)


def test_switching_knowledge_base_never_reuses_another_conversation():
    state = {}
    initialize_state(state)
    switch_knowledge_base(state, "kb-1")
    set_conversation_id(state, "conv-1")
    append_message(state, role="user", content="first")

    switch_knowledge_base(state, "kb-2")

    assert state["conversation_id"] is None
    assert state["messages"] == []


def test_switching_back_restores_only_that_knowledge_base_session():
    state = {}
    switch_knowledge_base(state, "kb-1")
    set_conversation_id(state, "conv-1")
    append_message(state, role="assistant", content="answer one")
    switch_knowledge_base(state, "kb-2")
    set_conversation_id(state, "conv-2")
    append_message(state, role="assistant", content="answer two")

    switch_knowledge_base(state, "kb-1")

    assert state["conversation_id"] == "conv-1"
    assert state["messages"][0]["content"] == "answer one"


def test_clear_current_chat_does_not_clear_other_knowledge_base():
    state = {}
    switch_knowledge_base(state, "kb-1")
    set_conversation_id(state, "conv-1")
    switch_knowledge_base(state, "kb-2")
    set_conversation_id(state, "conv-2")
    clear_current_chat(state)
    switch_knowledge_base(state, "kb-1")

    assert state["conversation_id"] == "conv-1"


@pytest.mark.parametrize("page", [None, -1, 0])
def test_missing_or_internal_page_value_is_user_friendly(page):
    source = normalize_source(
        {
            "source_id": "S1",
            "file_name": None,
            "page": page,
            "content": None,
        }
    )

    assert source["file_name"] == "未命名文档"
    assert source["page_label"] == "无页码"
    assert source["content"] == "暂无证据片段"


def test_real_page_number_is_not_shifted():
    source = normalize_source({"page": 3})
    assert source["page_label"] == "第 3 页"


def test_source_path_is_reduced_to_readable_file_name():
    source = normalize_source(
        {"file_name": r"D:\uploads\hash-value.txt"}
    )
    assert source["file_name"] == "hash-value.txt"


@pytest.mark.parametrize(
    "status,expected_label",
    [
        ("pending", "等待处理"),
        ("running", "正在入库"),
        ("succeeded", "入库成功"),
        ("failed", "入库失败"),
        ("unexpected", "状态未知"),
    ],
)
def test_ingestion_status_copy_has_clear_label(status, expected_label):
    label, guidance = ingestion_status_copy(status, "network error")
    assert label == expected_label
    assert guidance


def test_ingestion_task_is_scoped_by_knowledge_base():
    state = {}
    set_ingestion_task(state, "kb-1", {"task_id": "task-1"})
    set_ingestion_task(state, "kb-2", {"task_id": "task-2"})

    assert get_ingestion_task(state, "kb-1")["task_id"] == "task-1"
    assert get_ingestion_task(state, "kb-2")["task_id"] == "task-2"
