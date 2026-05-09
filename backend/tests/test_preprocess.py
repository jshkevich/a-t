from app.nlp.preprocess import preprocess_text


def test_preprocess_returns_lemmas_for_russian_words():
    lemmas = preprocess_text("Я писал код и тестировал приложение вчера.")
    assert "писать" in lemmas
    assert "код" in lemmas

