from app.services.chunkers.chunker import split_text


def test_split_text():

    text = "abcdefghijklmnopqrstuvwxyz" * 10

    chunks = split_text(
        text=text,
        document_id="doc001",
        chunk_size=50,
        chunk_overlap=10,
    )

    assert len(chunks) > 1

    assert chunks[0].document_id == "doc001"

    assert chunks[0].chunk_id == "doc001_0"

    assert chunks[0].start_index == 0

    assert chunks[0].content