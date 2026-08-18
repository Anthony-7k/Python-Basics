from unittest.mock import MagicMock

import pytest

from app.services.conversations.query_rewriter import (
    condense_question,
    estimate_text_tokens,
    fit_context_to_token_budget,
)


FOLLOW_UP_CASES = [
    (
        "年假按员工类型有什么区别？",
        "正式员工呢？",
        "正式员工的年假规定是什么？",
        "正式员工",
    ),
    (
        "正式员工试用期为三个月。",
        "那试用期呢？",
        "正式员工的试用期规定是什么？",
        "试用期",
    ),
    (
        "年假按累计工龄计算。",
        "上一条的来源是什么？",
        "年假按累计工龄计算这一规定的来源是什么？",
        "累计工龄",
    ),
    (
        "员工工作满十年享有十天年假。",
        "不满十年的情况呢？",
        "工作不满十年的员工享有多少天年假？",
        "不满十年",
    ),
    (
        "病假需要提交医疗证明。",
        "需要提前几天？",
        "申请病假需要提前几天？",
        "病假",
    ),
    (
        "差旅住宿标准按城市等级划分。",
        "北京是多少？",
        "北京的差旅住宿标准是多少？",
        "北京",
    ),
    (
        "报销应在费用发生后三十天内提交。",
        "逾期会怎样？",
        "报销超过三十天提交会怎样？",
        "报销",
    ),
    (
        "公司允许每周两天远程办公。",
        "新员工也可以吗？",
        "新员工是否可以每周两天远程办公？",
        "远程办公",
    ),
    (
        "绩效等级分为 A、B、C。",
        "B 对应什么？",
        "绩效等级 B 对应什么评价？",
        "绩效等级",
    ),
    (
        "培训预算按部门年度计划审批。",
        "换个话题，离职要提前多久？",
        "员工离职需要提前多久提出？",
        "离职",
    ),
]


def test_empty_history_keeps_original_question():
    generator = MagicMock()

    result = condense_question(
        history=[],
        current_question="员工有多少天年假？",
        llm_generate=generator,
    )

    assert result == "员工有多少天年假？"
    generator.assert_not_called()


def test_rewrite_failure_falls_back_to_original():
    def failed_generator(
        system_prompt,
        user_prompt,
    ):
        raise RuntimeError("rewrite failed")

    result = condense_question(
        history=[
            {
                "role": "user",
                "content": "年假怎么计算？",
            }
        ],
        current_question="正式员工呢？",
        llm_generate=failed_generator,
    )

    assert result == "正式员工呢？"


@pytest.mark.parametrize(
    (
        "history_content",
        "follow_up",
        "standalone",
        "expected_topic",
    ),
    FOLLOW_UP_CASES,
)
def test_follow_up_rewrite_hits_expected_topic(
    history_content,
    follow_up,
    standalone,
    expected_topic,
):
    def fake_generator(
        system_prompt,
        user_prompt,
    ):
        assert history_content in user_prompt
        assert follow_up in user_prompt
        return standalone

    result = condense_question(
        history=[
            {
                "role": "assistant",
                "content": history_content,
            }
        ],
        current_question=follow_up,
        llm_generate=fake_generator,
    )

    assert expected_topic in result


def test_history_payload_obeys_token_budget():
    history = [
        {
            "role": "user",
            "content": "旧主题" * 100,
        },
        {
            "role": "assistant",
            "content": "最近主题",
        },
    ]

    bounded_history, bounded_summary = (
        fit_context_to_token_budget(
            history=history,
            conversation_summary=(
                "已有摘要"
            ),
            token_budget=30,
        )
    )

    payload = "".join(
        str(item["content"])
        for item in bounded_history
    ) + (bounded_summary or "")

    assert "最近主题" in payload
    assert "旧主题" not in payload
    assert estimate_text_tokens(payload) <= 30
