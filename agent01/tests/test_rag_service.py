from unittest.mock import patch

from app.services.rag.rag_service import (
    answer_question,
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
