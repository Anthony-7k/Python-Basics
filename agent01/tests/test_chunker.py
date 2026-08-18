from app.services.chunkers.chunker import split_text


def test_split_text():

    text = "abcdefghijklmnopqrstuvwxyz" * 10

    chunks = split_text(
        text=text,
        document_id="doc001",
        knowledge_base_id="kb-a",
        chunk_size=50,
        chunk_overlap=10,
    )

    assert len(chunks) > 1

    assert chunks[0].document_id == "doc001"

    assert chunks[0].chunk_id == "doc001_0"

    assert chunks[0].start_index == 0

    assert chunks[0].content

def test_split_text_chunk_id_with_page():
    page1_chunks = split_text(
        text="第一页内容",
        document_id="pdf001",
        knowledge_base_id="kb-a",
        page=1,
    )

    page2_chunks = split_text(
        text="第二页内容",
        document_id="pdf001",
        knowledge_base_id="kb-a",
        page=2,
    )

    assert page1_chunks[0].chunk_id == "pdf001_p1_0"
    assert page2_chunks[0].chunk_id == "pdf001_p2_0"

    assert (
        page1_chunks[0].chunk_id
        != page2_chunks[0].chunk_id
    )
