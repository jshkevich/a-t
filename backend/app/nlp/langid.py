from __future__ import annotations

import re


_RE_RU = re.compile(r"[а-яё]", re.IGNORECASE)
_RE_EN = re.compile(r"[a-z]", re.IGNORECASE)


def detect_language(text: str) -> tuple[str, float]:
    """Очень лёгкая языковая идентификация для RU/EN/mixed/unknown.

    Возвращает (label, confidence), где confidence ∈ [0..1].
    """
    if not text:
        return "unknown", 0.0

    ru = len(_RE_RU.findall(text))
    en = len(_RE_EN.findall(text))
    total = ru + en
    if total == 0:
        return "unknown", 0.0

    ru_ratio = ru / total
    en_ratio = en / total

    if ru_ratio >= 0.8:
        return "ru", round(ru_ratio, 2)
    if en_ratio >= 0.8:
        return "en", round(en_ratio, 2)
    return "mixed", round(max(ru_ratio, en_ratio), 2)

