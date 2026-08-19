from types import SimpleNamespace
from unittest.mock import patch

from app.services.rag.rag_service import (
    answer_question,
    retrieve_context,
)


def test_rag_retrieves_with_standalone_and_answers_original(
    caplog,
):
    retrieval_result = {
        "context": "[S1]\n正式员工享有年假。",
        "sources": [
            {
                "source_id": "S1",
                "chunk_id": "chunk-1",
                "content": "正式员工享有年假。",
                "metadata": {
                    "source": "handbook.txt",
                    "page": 1,
                },
            }
        ],
    }

    caplog.set_level("INFO")

    with patch(
        "app.services.rag.rag_service."
        "retrieve_context",
        return_value=retrieval_result,
    ) as mocked_retrieve, patch(
        "app.services.rag.rag_service."
        "generate_answer",
        return_value="正式员工享有年假。[S1]",
    ) as mocked_generate:
        response = answer_question(
            knowledge_base_id="kb-a",
            original_question="正式员工呢？",
            standalone_question=(
                "正式员工的年假规定是什么？"
            ),
            request_id="day12-request",
        )

    mocked_retrieve.assert_called_once_with(
        question=(
            "正式员工的年假规定是什么？"
        ),
        knowledge_base_id="kb-a",
        knowledge_base_version=1,
        top_k=5,
    )
    user_prompt = (
        mocked_generate.call_args.kwargs[
            "user_prompt"
        ]
    )

    assert "正式员工呢？" in user_prompt
    assert (
        "正式员工的年假规定是什么？"
        in user_prompt
    )
    assert "用户原始问题" in user_prompt
    assert "用于理解上下文的独立问题" in (
        user_prompt
    )
    assert response.used_chunk_ids == [
        "chunk-1"
    ]
    assert "original_question='正式员工呢？'" in (
        caplog.text
    )
    assert (
        "standalone_question="
        "'正式员工的年假规定是什么？'"
        in caplog.text
    )


def test_retrieve_context_uses_configured_distance():
    outcome = SimpleNamespace(
        items=[
            {
                "chunk_id": "chunk-1",
                "content": "住宿上限为 880 元。",
                "distance": 1.04592,
                "metadata": {
                    "source": "policy.txt",
                },
            }
        ],
        cache_hit=False,
        cache_lookup_ms=1.0,
        retrieval_ms=2.0,
    )

    with patch(
        "app.services.rag.rag_service."
        "retrieve_with_cache",
        return_value=outcome,
    ) as mocked_retrieve:
        result = retrieve_context(
            question="上海住宿上限是多少？",
            knowledge_base_id="kb-a",
            knowledge_base_version=2,
        )

    assert (
        mocked_retrieve.call_args.kwargs[
            "max_distance"
        ]
        == 1.1
    )
    assert "880 元" in result["context"]
