import hashlib
import json
import re
from collections import Counter, OrderedDict
from pathlib import Path

from app.nlp.preprocess import preprocess_text

# Загрузка словаря интересов
_INTERESTS_PATH = Path(__file__).parent / "interests_list.json"
with open(_INTERESTS_PATH, "r", encoding="utf-8") as _f:
    _INTERESTS_DATA = json.load(_f)

# Плоский список: id → {name, category, keywords}
INTERESTS_BY_ID: dict[int, dict] = {item["id"]: item for item in _INTERESTS_DATA["interests"]}
# Индекс: keyword_lower → list[interest_id]
_KEYWORD_TO_INTERESTS: dict[str, list[int]] = {}
for item in _INTERESTS_DATA["interests"]:
    for kw in item["keywords"]:
        _KEYWORD_TO_INTERESTS.setdefault(kw.lower(), []).append(item["id"])


def load_interests_list() -> list[dict]:
    """Загрузить полный словарь интересов из JSON."""
    return _INTERESTS_DATA["interests"]


def match_interests(text: str, top_n: int = 8) -> list[dict]:
    """Найти интересы по тексту (кейворд-матч).

    Возвращает список словарей {id, name, category, score}, отсортированных по убыванию score.
    """
    text_lower = (text or "").lower()
    lemmas = preprocess_text(text_lower)
    if not lemmas:
        return []

    lemma_counts = Counter(lemmas)
    # Для фразовых keywords делаем быстрый поиск по леммам (n-gram).
    lemma_seq = " " + " ".join(lemmas) + " "

    scores: dict[int, float] = {}
    hit_keywords: dict[int, set[str]] = {}

    for keyword, interest_ids in _KEYWORD_TO_INTERESTS.items():
        kw = keyword.strip().lower()
        if not kw:
            continue

        # 1) Одно слово: матчим по леммам (строго, без substring-ложных срабатываний)
        if " " not in kw and "-" not in kw:
            count = lemma_counts.get(kw, 0)
        else:
            # 2) Фраза: пытаемся матчинуть как фрагмент в лемматизированной последовательности
            kw_lemmas = preprocess_text(kw)
            if not kw_lemmas:
                count = 0
            else:
                needle = " " + " ".join(kw_lemmas) + " "
                count = lemma_seq.count(needle)

        if count <= 0:
            continue

        # Длинные фразы немного усиливаем, одиночные слова — ослабляем
        weight = 1.0 + (0.2 * max(len(kw.split()) - 1, 0))
        weighted = float(count) * weight

        for iid in interest_ids:
            scores[iid] = scores.get(iid, 0.0) + weighted
            hit_keywords.setdefault(iid, set()).add(kw)

    if not scores:
        return []

    # Фильтр от ложноположительных: требуем минимум 2 разных ключа либо высокий скор
    filtered: dict[int, float] = {}
    for iid, score in scores.items():
        uniq = len(hit_keywords.get(iid, set()))
        if uniq >= 2 or score >= 3.0:
            filtered[iid] = score

    if not filtered:
        return []

    # Нормализация: score / max_score
    max_score = max(filtered.values()) or 1.0
    results = []
    for iid, score in sorted(filtered.items(), key=lambda x: x[1], reverse=True)[:top_n]:
        interest = INTERESTS_BY_ID[iid]
        results.append({
            "id": interest["id"],
            "name": interest["name"],
            "category": interest["category"],
            "score": round(score / max_score, 2),
        })

    return results


def get_interest_names_for_profession(interests: list[dict]) -> str:
    """Собрать имена интересов в строку для маппинга на профессию."""
    return " ".join(item["name"].lower() for item in interests)


# Маппинг эмоций → тональность (positive / neutral / negative)
EMOTION_TO_SENTIMENT = {
    # positive
    "радость": "positive",
    "счастье": "positive",
    "удовольствие": "positive",
    "восхищение": "positive",
    "восторг": "positive",
    "обожание": "positive",
    "любовь": "positive",
    "нежность": "positive",
    "благодарность": "positive",
    "удивление": "positive",
    "интерес": "positive",
    "увлечение": "positive",
    "надежда": "positive",
    "решимость": "positive",
    "гордость": "positive",
    # neutral
    "нейтральное": "neutral",
    "спокойствие": "neutral",
    "безразличие": "neutral",
    "забота": "neutral",
    "принятие": "neutral",
    # negative
    "грусть": "negative",
    "печаль": "negative",
    "гнев": "negative",
    "злость": "negative",
    "раздражение": "negative",
    "страх": "negative",
    "тревога": "negative",
    "отвращение": "negative",
    "стыд": "negative",
    "вина": "negative",
    "скука": "negative",
    "усталость": "negative",
    "разочарование": "negative",
    "одиночество": "negative",
    "ревность": "negative",
}

# Маппинг интересов на вероятные профессии (None = нет однозначной привязки)
PROFESSION_MAP = {
    "программирование": "Разработчик / IT-специалист",
    "код": "Разработчик / IT-специалист",
    "разработка": "Разработчик / IT-специалист",
    "игра": "Геймдизайнер / Киберспортсмен",
    "гейминг": "Геймдизайнер / Киберспортсмен",
    "наука": "Учёный / Инженер-исследователь",
    "исследование": "Учёный / Инженер-исследователь",
    "физика": "Учёный / Инженер-исследователь",
    "музыка": "Музыкант / Звукорежиссёр",
    "кино": "Кинематографист / Контент-мейкер",
    "аниме": "Кинематографист / Контент-мейкер",
    "фильм": "Кинематографист / Контент-мейкер",
    "спорт": "Спортсмен / Фитнес-тренер",
    "тренировка": "Спортсмен / Фитнес-тренер",
    "фитнес": "Спортсмен / Фитнес-тренер",
    "политика": "Политик / Журналист / Общественный деятель",
    "дизайн": "Дизайнер / Художник",
    "рисование": "Дизайнер / Художник",
    "искусство": "Дизайнер / Художник",
    "еда": "Шеф-повар / Фуд-блогер",
    "рецепт": "Шеф-повар / Фуд-блогер",
    "готовка": "Шеф-повар / Фуд-блогер",
    "кулинария": "Шеф-повар / Фуд-блогер",
    "автомобиль": "Автоинженер / Автомеханик",
    "машина": "Автоинженер / Автомеханик",
    "путешествие": "Турагент / Тревел-блогер",
    "туризм": "Турагент / Тревел-блогер",
    "финансы": "Финансист / Трейдер / Аналитик",
    "инвестиция": "Финансист / Трейдер / Аналитик",
    "обучение": "Преподаватель / Наставник",
    "учёба": "Преподаватель / Наставник",
    "медицина": "Врач / Медицинский специалист",
    "лечение": "Врач / Медицинский специалист",
    "здоровье": "Врач / Медицинский специалист",
}

# Стоп-слова для очистки меток кластеров
_LABEL_STOP_WORDS = frozenset({
    "это", "что", "как", "для", "но", "не", "на", "по", "с", "к", "у", "и", "а", "о",
    "в", "из", "за", "от", "до", "при", "про", "без", "чем", "либо", "нибудь", "тот",
    "этот", "мой", "твой", "его", "её", "наш", "их", "свой", "все", "весь", "сам",
    "очень", "тоже", "также", "ещё", "уже", "потом", "тут", "там", "где", "когда",
    "только", "просто", "даже", "почему", "потому", "значит", "вроде", "скорее",
    "кстати", "между", "через", "после", "перед", "между", "прямо", "обычно",
    "всё", "может", "будет", "было", "быть", "могу", "можешь", "надо", "нужно",
    "хотеть", "хочется", "делать", "сделать", "знать", "понимать", "думать", "говорить",
    "сказать", "видеть", "смотреть", "идти", "прийти", "взять", "дать", "стать",
    "вот", "да", "нет", "ну", "типа", "короче", "блин", "вообще", "ладно", "окей",
    "хорошо", "привет", "спасибо", "пожалуйста", "ладно", "конечно", "нормально",
})
