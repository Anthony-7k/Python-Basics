from app.services.cleaners.text_cleaner import clean_text


def test_clean_text():
    text = """
    Hello     world


    test
    """

    result = clean_text(text)

    assert result == "Hello world\n\ntest"