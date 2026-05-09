import re
from functools import lru_cache

import pymorphy3

from app.nlp.langid import detect_language


@lru_cache(maxsize=1)
def get_morph():
    return pymorphy3.MorphAnalyzer()


def preprocess_text(text: str) -> list[str]:
    text = text.lower()
    lang, _conf = detect_language(text)

    if lang == "en":
        words = re.findall(r"[a-z]+", text)
        return [w for w in words if len(w) > 2]

    # ru / mixed / unknown → стараемся извлечь русские леммы, а латиницу игнорируем
    words = re.findall(r"[а-яё]+", text)
    morph = get_morph()
    return [morph.parse(word)[0].normal_form for word in words if len(word) > 2]

