from app.services.loaders.txt_loader import load_txt


def test_txt_loader():

    doc = load_txt(
        "data/sample/test.txt"
    )

    print(doc)

    assert doc.content != ""
    assert doc.file_name == "test.txt"