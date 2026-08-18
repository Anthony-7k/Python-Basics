from app.cli import run_ingest, run_chat
from app.schemas.rag import RAGResponse, RAGSource


def test_run_ingest(
    monkeypatch,
    capsys,
    tmp_path,
):
    def fake_ingest_file(
        file_path,
        document_id,
        knowledge_base_id,
    ):
        return ["chunk1", "chunk2"]

    monkeypatch.setattr(
        "app.cli.ingest_file",
        fake_ingest_file,
    )

    file_path = tmp_path / "test.txt"
    file_path.write_text(
        "test content",
        encoding="utf-8",
    )
    run_ingest(
        str(file_path),
        knowledge_base_id="kb-a",
    )

    output = capsys.readouterr().out

    assert "Ingestion completed" in output
    assert "Chunks: 2" in output


def test_run_chat_with_source(monkeypatch, capsys):
    def fake_answer_question(
        question,
        top_k=5,
        *,
        knowledge_base_id,
    ):
        return RAGResponse(
            answer="员工享有10天带薪年假。[S1]",
            sources=[
                RAGSource(
                    source_id="S1",
                    chunk_id="chunk-1",
                    file_name="employee_handbook.txt",
                    page=1,
                    content="员工享有10天带薪年假。",
                )
            ],
            used_chunk_ids=["chunk-1"],
            request_id="test-request-id",
        )

    monkeypatch.setattr(
        "app.cli.answer_question",
        fake_answer_question,
    )

    run_chat(
        question="员工有多少天年假？",
        top_k=5,
        knowledge_base_id="kb-a",
    )

    output = capsys.readouterr().out

    assert "员工享有10天带薪年假" in output
    assert "employee_handbook.txt" in output
    assert "test-request-id" in output


def test_run_chat_without_source(monkeypatch, capsys):
    def fake_answer_question(
        question,
        top_k=5,
        *,
        knowledge_base_id,
    ):
        return RAGResponse(
            answer="知识库中没有足够的信息回答这个问题。",
            sources=[],
            used_chunk_ids=[],
            request_id="test-refusal-id",
        )

    monkeypatch.setattr(
        "app.cli.answer_question",
        fake_answer_question,
    )

    run_chat(
        question="公司提供免费健身房吗？",
        top_k=5,
        knowledge_base_id="kb-a",
    )

    output = capsys.readouterr().out

    assert "知识库中没有足够的信息" in output
    assert "No sources" in output
    assert "test-refusal-id" in output
