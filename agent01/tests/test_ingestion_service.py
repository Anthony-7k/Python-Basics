from app.services.ingestion.ingestion_service import build_chunks


def test_build_chunks_uses_original_upload_name_for_citations(tmp_path):
    stored_file = tmp_path / "content-hash.txt"
    stored_file.write_text(
        "Employees receive five days of annual leave after one year.",
        encoding="utf-8",
    )

    chunks = build_chunks(
        str(stored_file),
        document_id="doc-1",
        knowledge_base_id="kb-1",
        display_file_name="employee_handbook.txt",
    )

    assert chunks
    assert all(chunk.source == "employee_handbook.txt" for chunk in chunks)
