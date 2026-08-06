from app.services.loaders.pdf_loader import load_pdf


def test_pdf_loader():

    docs = load_pdf(
        "data/sample/test.pdf"
    )

    print(docs)

    assert len(docs) > 0

    assert docs[0].content != ""