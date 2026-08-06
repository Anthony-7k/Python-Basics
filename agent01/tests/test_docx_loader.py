from app.services.loaders.docx_loader import load_docx


def test_docx_loader():
    docs = load_docx(
        "data/sample/test.docx"
    )

    assert len(docs) == 1
    assert docs[0].file_name == "test.docx"
    assert docs[0].content == "这是一个测试Word文件"