import hashlib
import json
import logging
import re
import spacy
from collections import Counter, OrderedDict
from functools import lru_cache
from pathlib import Path
from threading import Lock
from time import perf_counter

from fastapi import HTTPException
from sentence_transformers import util
from sklearn.feature_extraction.text import TfidfVectorizer
from transformers import pipeline

from app.config import settings
from app.interests import EMOTION_TO_SENTIMENT, match_interests
from app.importer.telegram_export import extract_text
from app.nlp.models import get_embedding_model, get_emotion_pipeline
from app.nlp.langid import detect_language
from app.nlp.preprocess import get_morph, preprocess_text
from app.schemas import (
    AnalysisMeta,
    Demographics,
    EmotionScore,
    InterestScore,
    KeywordScore,
    NlpAnalysis,
    ProfileAnalysisResponse,
    SpeechPatternScore,
    Tonality,
)

_cache: OrderedDict[str, ProfileAnalysisResponse] = OrderedDict()
_cache_lock = Lock()
_semantic_embeddings_cache: OrderedDict[str, tuple[list[str], object, list[set[str]]]] = OrderedDict()
_semantic_cache_lock = Lock()

# spaCy handles language stop words. These sets only remove chat/domain noise
# that is often meaningful syntactically but not useful as profile evidence.
CHAT_NOISE_WORDS = frozenset({
    "согл", "жиза", "норма", "капец", "блин", "кстати", "вообще", "типа",
    "ок", "оке", "ясно", "пон", "понятно", "плз", "спс", "привет", "пока",
    "чел", "челик", "туда", "сюда", "тупо", "реально", "ща", "щас", "щаз",
    "че", "чо", "ладно", "короче",
})
DOMAIN_GENERIC_WORDS = frozenset({
    "это", "который", "человек", "мочь", "свой", "просто", "спасибо",
    "сегодня", "вчера", "завтра", "тип", "слово", "дело", "время", "день",
    "хотеть", "делать", "сказать", "говорить", "идти", "взять",
})
CUSTOM_NOISE_WORDS = CHAT_NOISE_WORDS | DOMAIN_GENERIC_WORDS
logger = logging.getLogger(__name__)
_APP_DIR = Path(__file__).resolve().parents[1]
_INTERESTS_PATH = _APP_DIR / "interests_list.json"
_OCCUPATIONS_PATH = _APP_DIR / "occupations_list.json"


def _make_cache_key(username: str, messages: list[str]) -> str:
    payload = {"username": username, "messages": messages}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode("utf-8")).hexdigest()


def _cache_get(key: str):
    with _cache_lock:
        if key not in _cache:
            return None
        value = _cache.pop(key)
        _cache[key] = value
        return value


def _cache_set(key: str, value: ProfileAnalysisResponse):
    with _cache_lock:
        _cache[key] = value
        if len(_cache) > settings.analysis_cache_size:
            _cache.popitem(last=False)


def _make_messages_key(messages: list[str]) -> str:
    payload = {
        "embedding_model": getattr(settings, "embedding_model_name", ""),
        "embedding_fallback_model": getattr(settings, "embedding_model_fallback_name", ""),
        "messages": messages,
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode("utf-8")).hexdigest()


def _semantic_cache_get(key: str):
    with _semantic_cache_lock:
        if key not in _semantic_embeddings_cache:
            return None
        value = _semantic_embeddings_cache.pop(key)
        _semantic_embeddings_cache[key] = value
        return value


def _semantic_cache_set(key: str, value):
    with _semantic_cache_lock:
        _semantic_embeddings_cache[key] = value
        if len(_semantic_embeddings_cache) > settings.semantic_cache_size:
            _semantic_embeddings_cache.popitem(last=False)


def _unknown_interest() -> InterestScore:
    return InterestScore(name="Интересы не выражены", confidence=0.0)


def _is_placeholder_interest(interest: InterestScore) -> bool:
    return interest.confidence <= 0.0 or interest.name.lower().startswith(
        ("мало данных", "интересы не выражены")
    )


def _is_unknown_occupation(value: str, confidence: float) -> bool:
    return confidence <= 0.0 or value.strip().lower().startswith("не определ")


def _clamp_confidence(value, default: float = 0.0) -> float:
    try:
        return max(0.0, min(float(value), 1.0))
    except (TypeError, ValueError):
        return default


def _is_noise_lemma(lemma: str) -> bool:
    return len(lemma) <= 2 or lemma.lower() in CUSTOM_NOISE_WORDS


def _has_confident_interests(interests: list[InterestScore], threshold: float = 0.45) -> bool:
    return any(not _is_placeholder_interest(interest) and interest.confidence >= threshold for interest in interests)


@lru_cache(maxsize=1)
def _load_interest_taxonomy() -> tuple[dict, ...]:
    try:
        data = json.loads(_INTERESTS_PATH.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to load interests taxonomy")
        return ()

    items = []
    for item in data.get("interests", []):
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        keywords = [str(keyword) for keyword in item.get("keywords", []) if str(keyword).strip()]
        description = str(item.get("description", "")).strip()
        text_parts = [
            name,
            description,
            " ".join(keywords[:20]),
            str(item.get("category", "")),
        ]
        items.append({**item, "name": name, "embedding_text": ". ".join(part for part in text_parts if part)})
    return tuple(items)


@lru_cache(maxsize=1)
def _load_occupation_taxonomy() -> tuple[dict, ...]:
    try:
        data = json.loads(_OCCUPATIONS_PATH.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to load occupations taxonomy")
        return ()

    items = []
    for item in data.get("occupations", []):
        name = str(item.get("name", "")).strip()
        description = str(item.get("description", "")).strip()
        if not name or not description:
            continue
        items.append({**item, "name": name, "embedding_text": f"{name}. {description}"})
    return tuple(items)


@lru_cache(maxsize=4)
def _taxonomy_embeddings(kind: str, model_name: str) -> tuple[tuple[dict, ...], object | None]:
    items = _load_interest_taxonomy() if kind == "interest" else _load_occupation_taxonomy()
    if not items:
        return items, None

    try:
        model = get_embedding_model()
        texts = [item["embedding_text"] for item in items]
        embeddings = model.encode(texts, convert_to_tensor=True, normalize_embeddings=True)
        return items, embeddings
    except Exception:
        logger.exception("Failed to encode %s taxonomy", kind)
        return items, None


def _build_profile_embedding_text(signal_context: dict) -> str:
    messages = signal_context.get("qa_source_messages", [])
    parts = [
        "Ключевые слова: " + ", ".join(signal_context.get("keywords", [])[:24]),
        "Частые слова: " + ", ".join(signal_context.get("frequent_keywords", [])[:24]),
        "Сообщения: " + " ".join(str(message) for message in messages[:18]),
    ]
    return "\n".join(part for part in parts if part.strip())[:4500]


def _rank_taxonomy(kind: str, profile_text: str, top_n: int = 8) -> list[dict]:
    clean_text = (profile_text or "").strip()
    if not clean_text:
        return []

    try:
        model = get_embedding_model()
        model_name = getattr(settings, "embedding_model_name", "") or model.__class__.__name__
        items, item_embeddings = _taxonomy_embeddings(kind, model_name)
        if item_embeddings is None:
            return []

        query_embedding = model.encode([clean_text], convert_to_tensor=True, normalize_embeddings=True)
        scores = util.cos_sim(query_embedding, item_embeddings)[0].tolist()
    except Exception:
        logger.exception("Taxonomy ranking failed: %s", kind)
        return []

    ranked = []
    for item, score in zip(items, scores, strict=False):
        confidence = _clamp_confidence((float(score) + 1.0) / 2.0)
        ranked.append({**item, "confidence": confidence, "similarity": float(score)})

    ranked.sort(key=lambda item: item["confidence"], reverse=True)
    return ranked[:top_n]


def analyze_profile(username: str, messages: list[str]) -> ProfileAnalysisResponse:
    started = perf_counter()
    logger.info("Analyze profile started: username='%s', messages=%s", username, len(messages))
    if not messages:
        raise HTTPException(status_code=400, detail="Список сообщений пуст")

    cache_key = _make_cache_key(username, messages)
    cached = _cache_get(cache_key)
    if cached:
        logger.info("Analyze profile cache hit: username='%s'", username)
        return cached.model_copy(update={"meta": cached.meta.model_copy(update={"usedCache": True})})

    full_text_raw = " ".join(messages)
    lang, lang_conf = detect_language(full_text_raw)

    limited_for_patterns = messages[: settings.max_messages_for_patterns]
    limited_for_clustering = messages[: settings.max_messages_for_clustering]

    processed_messages = [preprocess_text(msg) for msg in limited_for_patterns]
    all_lemmas = [word for msg in processed_messages for word in msg]

    if not all_lemmas:
        raise HTTPException(status_code=400, detail="В сообщениях нет значимых слов для анализа")

    # 1. Эмоциональный анализ
    tonality, emotions = _analyze_emotions(messages)

    # 2. Ключевые слова (TF-IDF по всему корпусу)
    keywords = _extract_keywords(processed_messages)

    # 3. Интересы и занятость: локальный evidence pipeline + QA по сжатому контексту
    interests = _extract_interests_dynamic(messages)

    # 4. Речевые паттерны
    patterns = _extract_patterns(processed_messages)

    # 5. Демография + стиль
    gender, gender_conf = _detect_gender_smart(messages)
    comm_style, comm_style_conf = _analyze_communication_style_detailed(messages, tonality)

    age, age_conf = _detect_age_by_rubert(messages)

    occupation, occ_conf = _extract_occupation_smart(messages)

    age_conf = _clamp_confidence(age_conf)
    gender_conf = _clamp_confidence(gender_conf)
    occ_conf = _clamp_confidence(occ_conf)
    comm_style_conf = _clamp_confidence(comm_style_conf)

    response = ProfileAnalysisResponse(
        username=username,
        demographics=Demographics(
            age=age,
            ageConfidence=age_conf,
            gender=gender,
            genderConfidence=gender_conf,
            occupation=occupation,
            occupationConfidence=occ_conf,
        ),
        topicsAndInterests=interests if interests else [_unknown_interest()],
        nlpAnalysis=NlpAnalysis(
            tonality=Tonality(**tonality),
            emotions=emotions,
            communicationStyle=comm_style,
            communicationStyleConfidence=comm_style_conf,
            speechPatterns=patterns if patterns else [],
            keywords=keywords,
        ),
        meta=AnalysisMeta(
            usedCache=False,
            processedMessages=len(messages),
            messagesUsedForPatterns=min(len(processed_messages), settings.max_messages_for_patterns),
            messagesUsedForInterests=min(len(limited_for_clustering), len(messages)),
            sentimentSampleSize=min(len(messages), settings.emotion_sample_size),
            language=lang,
            languageConfidence=lang_conf,
        ),
    )
    _cache_set(cache_key, response)
    elapsed_ms = round((perf_counter() - started) * 1000)
    logger.info(
        "Analyze profile finished: username='%s', keywords=%s, interests=%s, patterns=%s, elapsed_ms=%s",
        username,
        len(response.nlpAnalysis.keywords),
        len(response.topicsAndInterests),
        len(response.nlpAnalysis.speechPatterns),
        elapsed_ms,
    )
    return response


# ---------------------------------------------------------------------------
# Эмоции (cointegrated/rubert-tiny2-cedr-emotion)
# ---------------------------------------------------------------------------

def _analyze_emotions(messages: list[str]) -> tuple[dict[str, int], list[dict]]:
    emotion_pipe = get_emotion_pipeline()
    if not emotion_pipe:
        return {"positive": 33, "neutral": 34, "negative": 33, "confidence": 0.0}, []

    sample = messages[-settings.emotion_sample_size:]
    try:
        results = emotion_pipe(sample)
    except Exception:
        return {"positive": 33, "neutral": 34, "negative": 33, "confidence": 0.0}, []

    emotion_totals: dict[str, float] = {}
    emotion_counts: dict[str, int] = {}
    for result in results:
        if not isinstance(result, list):
            result = [result]
        for r in result:
            label = _normalize_emotion_label(r["label"])
            emotion_totals[label] = emotion_totals.get(label, 0) + r["score"]
            emotion_counts[label] = emotion_counts.get(label, 0) + 1

    total_score = sum(emotion_totals.values()) or 1
    emotions_pct = {k: round((v / total_score) * 100) for k, v in emotion_totals.items()}

    sentiment = {"positive": 0, "neutral": 0, "negative": 0}
    for emotion, pct in emotions_pct.items():
        category = EMOTION_TO_SENTIMENT.get(emotion, "neutral")
        sentiment[category] += pct

    sent_total = max(sum(sentiment.values()), 1)
    tonality = {k: round(v / sent_total * 100) for k, v in sentiment.items()}
    tonality["confidence"] = round(max(tonality["positive"], tonality["neutral"], tonality["negative"]) / 100, 2)

    top_emotions = sorted(emotions_pct.items(), key=lambda x: x[1], reverse=True)
    emotions_list = [
        EmotionScore(
            label=label,
            percentage=pct,
            confidence=round((emotion_totals.get(label, 0.0) / max(emotion_counts.get(label, 1), 1)), 2),
        )
        for label, pct in top_emotions
        if pct >= 3
    ][:8]

    return tonality, [e.model_dump() for e in emotions_list]


# ---------------------------------------------------------------------------
# Ключевые слова
# ---------------------------------------------------------------------------

def _extract_keywords(processed_messages: list[list[str]]) -> list[dict]:
    started = perf_counter()
    all_lemmas = [word for msg in processed_messages for word in msg]
    if not all_lemmas:
        return [KeywordScore(keyword="анализ", confidence=0.0).model_dump()]

    try:
        morph = get_morph()
        
        # Собираем уникальные существительные из каждого сообщения 
        # (чтобы считалась частота по сообщениям, а не количество повторений в одном)
        document_nouns: list[str] = []
        for msg in processed_messages:
            unique_nouns_in_msg = set()
            for lemma in msg:
                if _is_noise_lemma(lemma):
                    continue
                parse = morph.parse(lemma)[0]
                if "NOUN" in parse.tag.grammemes:
                    unique_nouns_in_msg.add(parse.normal_form)
            document_nouns.extend(unique_nouns_in_msg)

        # Если нашли существительные — используем Counter вместо тяжелого itemset mining
        if document_nouns:
            counts = Counter(document_nouns)
            # Берем топ-12 самых частых слов
            top_singles = counts.most_common(12)
            
            if top_singles:
                # Максимальная частота для нормализации (уверенности)
                max_count = top_singles[0][1] 
                return [
                    KeywordScore(
                        keyword=word,
                        confidence=round(count / max_count, 2),
                    ).model_dump()
                    for word, count in top_singles
                ]

        # Fallback: TF-IDF по всем леммам (оставлен без изменений)
        vectorizer = TfidfVectorizer(max_features=200)
        tfidf = vectorizer.fit_transform([" ".join(all_lemmas)])
        feature_names = vectorizer.get_feature_names_out().tolist()
        scores = tfidf.toarray()[0]
        top_indices = scores.argsort()[-10:][::-1]
        top_pairs = [(feature_names[i], float(scores[i])) for i in top_indices if scores[i] > 0]
        max_score = max((s for _, s in top_pairs), default=0.0) or 1.0
        return [
            KeywordScore(keyword=w, confidence=round(s / max_score, 2)).model_dump()
            for w, s in top_pairs
        ]
    except Exception:
        # Добавлено логирование ошибки, чтобы не было "тихого" падения
        logger.exception("Keyword extraction failed, using fallback stub")
        return [KeywordScore(keyword="анализ", confidence=0.0).model_dump()]
    finally:
        logger.info(
            "Keyword extraction done: messages=%s, elapsed_ms=%s", 
            len(processed_messages), 
            round((perf_counter() - started) * 1000)
        )


def _extract_frequent_keywords(processed_messages: list[list[str]], limit: int = 20) -> list[str]:
    """Return bounded frequent terms for the QA context.

    Full FP-growth can explode on chat data with a wide vocabulary. For the QA
    context we only need stable topical signals, so document frequency is safer.
    """
    if not processed_messages:
        return []

    max_messages = min(len(processed_messages), settings.max_messages_for_patterns, 800)
    document_frequency = Counter()
    for msg in processed_messages[:max_messages]:
        terms = {word for word in msg if not _is_noise_lemma(word)}
        document_frequency.update(terms)

    min_count = 2 if max_messages >= 20 else 1
    return [
        word
        for word, count in document_frequency.most_common(limit)
        if count >= min_count
    ]


def _find_evidence_messages(messages: list[str], terms: list[str], limit: int = 3) -> list[str]:
    normalized_terms = [term.lower() for term in terms if term and len(term) > 2]
    if not normalized_terms:
        return []

    evidence = []
    for message in reversed(messages):
        text = str(message).strip()
        text_lower = text.lower()
        if any(term in text_lower for term in normalized_terms):
            evidence.append(text[:220])
        if len(evidence) >= limit:
            break
    return list(reversed(evidence))


def _select_qa_source_messages(messages: list[str], terms: list[str], limit: int = 18) -> list[str]:
    normalized_terms = [term.lower() for term in terms if term and len(term) > 2]
    selected: list[str] = []
    seen = set()

    for message in reversed(messages):
        text = str(message).strip()
        if not text or text in seen:
            continue
        text_lower = text.lower()
        if normalized_terms and any(term in text_lower for term in normalized_terms):
            selected.append(text[:260])
            seen.add(text)
        if len(selected) >= limit:
            break

    if len(selected) < min(6, limit):
        for message in reversed(messages):
            text = str(message).strip()
            if not text or text in seen:
                continue
            selected.append(text[:260])
            seen.add(text)
            if len(selected) >= limit:
                break

    return list(reversed(selected))


def _build_profile_signal_context(messages: list[str], processed_messages: list[list[str]]) -> dict:
    keyword_scores = _extract_keywords(processed_messages)
    keywords = [item["keyword"] for item in keyword_scores if item.get("confidence", 0.0) > 0]
    frequent_keywords = _extract_frequent_keywords(processed_messages)
    full_text = " ".join(messages)
    dictionary_text = " ".join([full_text, " ".join(keywords), " ".join(frequent_keywords)])
    qa_source_messages = _select_qa_source_messages(messages, [*keywords, *frequent_keywords])

    profile_stub = {
        "keywords": keywords,
        "frequent_keywords": frequent_keywords,
        "qa_source_messages": qa_source_messages,
    }
    profile_text = _build_profile_embedding_text(profile_stub)
    embedding_interests = _rank_taxonomy("interest", profile_text, top_n=12)
    interest_matches = match_interests(dictionary_text, top_n=10)

    interest_candidates_by_name: dict[str, dict] = {}
    for item in embedding_interests:
        evidence = _find_evidence_messages(messages, [item["name"], *keywords, *frequent_keywords])
        confidence = _clamp_confidence(item["confidence"])
        if evidence:
            confidence = _clamp_confidence(confidence + 0.04)
        interest_candidates_by_name[item["name"].lower()] = {
            "name": item["name"],
            "confidence": confidence,
            "embeddingScore": round(float(item.get("similarity", 0.0)), 4),
            "keywordScore": 0.0,
            "evidence": evidence,
        }

    for item in interest_matches:
        terms = [str(item["name"]), *keywords, *frequent_keywords]
        evidence = _find_evidence_messages(messages, terms)
        keyword_score = _clamp_confidence(float(item.get("score", 0.0)))
        score = _clamp_confidence(0.35 + (0.45 * keyword_score))
        if evidence:
            score = _clamp_confidence(score + 0.05)
        key = str(item["name"]).lower()
        existing = interest_candidates_by_name.get(key)
        if existing:
            existing["confidence"] = _clamp_confidence(max(existing["confidence"], score) + 0.08)
            existing["keywordScore"] = keyword_score
            if not existing["evidence"]:
                existing["evidence"] = evidence
        else:
            interest_candidates_by_name[key] = {
                "name": item["name"],
                "confidence": score,
                "embeddingScore": 0.0,
                "keywordScore": keyword_score,
                "evidence": evidence,
            }

    interest_candidates = list(interest_candidates_by_name.values())
    interest_candidates.sort(key=lambda item: item["confidence"], reverse=True)

    context_lines = [
        "Ключевые слова: " + ", ".join(keywords[:16]),
        "Частые слова: " + ", ".join(frequent_keywords[:16]),
        "Кандидаты интересов:",
    ]
    for item in interest_candidates[:8]:
        evidence = " | ".join(item["evidence"]) if item["evidence"] else "нет цитат"
        context_lines.append(f"- {item['name']} confidence={item['confidence']:.2f}; цитаты: {evidence}")

    context_lines.append("Сообщения-источники для QA:")
    for idx, message in enumerate(qa_source_messages, start=1):
        context_lines.append(f"{idx}. {message}")

    return {
        "keyword_scores": keyword_scores,
        "keywords": keywords,
        "frequent_keywords": frequent_keywords,
        "interests": interest_candidates,
        "qa_source_messages": qa_source_messages,
        "profile_text": profile_text,
        "context": "\n".join(context_lines)[:5000],
    }


def _qa_select_from_candidates(question: str, context: str, candidates: list[dict]) -> dict | None:
    if not candidates:
        return None

    qa = get_model("qa")
    if not qa:
        return None

    try:
        answer = qa(question=question, context=context)
    except Exception:
        logger.exception("QA candidate selection failed")
        return None

    answer_text = str(answer.get("answer", "")).lower()
    answer_score = _clamp_confidence(answer.get("score"), 0.0)
    if not answer_text or answer_score < 0.08:
        return None

    for candidate in candidates:
        name = str(candidate["name"])
        if name.lower() in answer_text or any(part.lower() in answer_text for part in name.split("/") if len(part.strip()) > 4):
            selected = candidate.copy()
            selected["confidence"] = _clamp_confidence(max(float(candidate["confidence"]), answer_score))
            return selected
    return None


def _extract_interests_from_signal_context(signal_context: dict) -> list[InterestScore]:
    candidates = signal_context.get("interests", [])
    if not candidates:
        return [_unknown_interest()]

    selected = _qa_select_from_candidates(
        "Какой главный интерес пользователя указан в кандидатах интересов?",
        signal_context.get("context", ""),
        candidates,
    )

    ranked = candidates[:]
    if selected:
        ranked = [
            selected if item["name"] == selected["name"] else item
            for item in ranked
        ]
        ranked.sort(key=lambda item: item["confidence"], reverse=True)

    results = [
        InterestScore(name=item["name"], confidence=_clamp_confidence(item["confidence"]))
        for item in ranked[:8]
        if float(item.get("confidence", 0.0)) >= 0.52
    ]
    return results or [_unknown_interest()]


def _select_ranked_occupation(signal_context: dict) -> tuple[str, float]:
    profile_text = signal_context.get("profile_text") or _build_profile_embedding_text(signal_context)
    ranked = _rank_taxonomy("occupation", profile_text, top_n=3)
    if not ranked:
        return "Не определена (мало данных)", 0.0

    best = ranked[0]
    second_conf = float(ranked[1]["confidence"]) if len(ranked) > 1 else 0.0
    confidence = _clamp_confidence(best.get("confidence"), 0.0)
    similarity = float(best.get("similarity", 0.0))
    margin = confidence - second_conf

    if similarity < 0.16 or confidence < 0.56 or margin < 0.025:
        return "Не определена (мало данных)", 0.0
    return str(best["name"]), confidence


def _extract_occupation_from_signal_context(signal_context: dict) -> tuple[str, float]:
    context = signal_context.get("context", "")
    if not context.strip():
        return "Не определена (мало данных)", 0.0

    qa = get_model("qa")
    if not qa:
        return "Не определена (мало данных)", 0.0

    questions = [
        "Кем работает пользователь?",
        "Какая профессия или занятость пользователя явно указана в сообщениях?",
        "Чем занимается пользователь?",
    ]

    best_answer = ""
    best_score = 0.0
    try:
        for question in questions:
            result = qa(question=question, context=context)
            score = _clamp_confidence(result.get("score"), 0.0)
            answer = str(result.get("answer", "")).strip().strip(".,!?:; ")
            if score > best_score:
                best_score = score
                best_answer = answer
    except Exception:
        logger.exception("Occupation QA over signal context failed")
        return "Не определена (мало данных)", 0.0

    if best_score < 0.18 or len(best_answer) < 3:
        return _select_ranked_occupation(signal_context)

    low = best_answer.lower()
    invalid_answers = {
        "не определена", "не определено", "нет", "нет данных", "данных мало",
        "пользователь", "сообщения", "ключевые слова",
    }
    if low in invalid_answers or low in CUSTOM_NOISE_WORDS:
        return _select_ranked_occupation(signal_context)

    return best_answer[:80].capitalize(), best_score


def semantic_search_messages(
    query: str,
    messages: list[str],
    top_k: int = 5,
    min_score: float = 0.2,
) -> list[dict]:
    started = perf_counter()
    logger.info(
        "Semantic search started: query_len=%s, messages=%s, top_k=%s, min_score=%.2f",
        len((query or "").strip()),
        len(messages),
        top_k,
        min_score,
    )
    clean_query = (query or "").strip()
    if not clean_query:
        raise HTTPException(status_code=400, detail="Пустой запрос semantic поиска")
    if not messages:
        raise HTTPException(status_code=400, detail="Нет сообщений для semantic поиска")

    model = get_embedding_model()
    indexed_candidates: list[tuple[int, str]] = [
        (i, m) for i, m in enumerate(messages) if isinstance(m, str) and m.strip()
    ]
    if not indexed_candidates:
        raise HTTPException(status_code=400, detail="Нет текстовых сообщений для semantic поиска")
    if len(indexed_candidates) > settings.semantic_max_messages:
        indexed_candidates = indexed_candidates[-settings.semantic_max_messages:]

    limit = max(1, min(int(top_k or 5), 20))
    floor = max(0.0, min(float(min_score or 0.0), 1.0))

    candidate_messages = [m for _, m in indexed_candidates]
    candidate_indices = [i for i, _ in indexed_candidates]

    messages_key = _make_messages_key(candidate_messages)
    cached_embeddings = _semantic_cache_get(messages_key)
    if cached_embeddings:
        cached_messages, message_embeddings, cached_token_sets = cached_embeddings
        logger.info("Semantic cache hit: messages=%s", len(cached_messages))
    else:
        cached_messages = candidate_messages
        embed_started = perf_counter()
        cached_token_sets = [set(preprocess_text(m)) for m in cached_messages]

        model_name = getattr(settings, "embedding_model_name", "") or ""
        use_e5_prefix = "e5" in model_name.lower()
        passages = [f"passage: {m}" if use_e5_prefix else m for m in cached_messages]
        message_embeddings = model.encode(passages, convert_to_tensor=True, normalize_embeddings=True)

        _semantic_cache_set(messages_key, (cached_messages, message_embeddings, cached_token_sets))
        logger.info(
            "Semantic cache miss: embedded_messages=%s, elapsed_ms=%s",
            len(cached_messages),
            round((perf_counter() - embed_started) * 1000),
        )

    query_tokens = set(preprocess_text(clean_query))
    model_name = getattr(settings, "embedding_model_name", "") or ""
    use_e5_prefix = "e5" in model_name.lower()
    query_text = f"query: {clean_query}" if use_e5_prefix else clean_query
    query_embedding = model.encode([query_text], convert_to_tensor=True, normalize_embeddings=True)
    sims = util.cos_sim(query_embedding, message_embeddings)[0]

    scored = []
    for idx, score in enumerate(sims.tolist()):
        cos_value = float(score)
        tokens = cached_token_sets[idx] if idx < len(cached_token_sets) else set()
        denom = max(len(query_tokens | tokens), 1)
        jaccard = (len(query_tokens & tokens) / denom) if query_tokens else 0.0
        value = 0.88 * cos_value + 0.12 * jaccard
        if value >= floor:
            scored.append(
                {
                    "message": cached_messages[idx],
                    "score": round(value, 4),
                    "index": int(candidate_indices[idx]) if idx < len(candidate_indices) else idx,
                }
            )

    scored.sort(key=lambda item: item["score"], reverse=True)
    result = scored[:limit]
    logger.info("Semantic search finished: returned=%s, elapsed_ms=%s", len(result), round((perf_counter() - started) * 1000))
    return result


def semantic_search_chat(
    chat: dict,
    query: str,
    top_users: int = 5,
    per_user_k: int = 2,
    min_score: float = 0.25,
) -> list[dict]:
    started = perf_counter()
    clean_query = (query or "").strip()
    if not clean_query:
        raise HTTPException(status_code=400, detail="Пустой запрос semantic поиска по чату")

    raw_messages = chat.get("messages", []) or []
    if not isinstance(raw_messages, list) or not raw_messages:
        raise HTTPException(status_code=400, detail="В чате нет сообщений для поиска")

    # Собираем кандидатов: (messageIndex в export, userId, userName, text)
    candidates: list[tuple[int, str, str, str]] = []
    for i, msg in enumerate(raw_messages):
        if not isinstance(msg, dict):
            continue
        if msg.get("type") != "message":
            continue
        uid = msg.get("from_id")
        name = msg.get("from")
        if not uid or not name:
            continue
        text = extract_text(msg.get("text"))
        if not text or not text.strip():
            continue
        candidates.append((i, str(uid), str(name), text))

    if not candidates:
        raise HTTPException(status_code=400, detail="Нет текстовых сообщений с отправителями для поиска")

    # Ограничиваем объём: берём хвост чата (обычно он наиболее актуален).
    if len(candidates) > settings.semantic_max_messages:
        candidates = candidates[-settings.semantic_max_messages :]

    limit_users = max(1, min(int(top_users or 5), 20))
    limit_per_user = max(1, min(int(per_user_k or 2), 5))
    floor = max(0.0, min(float(min_score or 0.0), 1.0))

    model = get_embedding_model()
    texts = [t for _, _, _, t in candidates]
    message_indices = [i for i, _, _, _ in candidates]
    user_ids = [uid for _, uid, _, _ in candidates]
    user_names = [name for _, _, name, _ in candidates]

    messages_key = _make_messages_key(texts)
    cached_embeddings = _semantic_cache_get(messages_key)
    if cached_embeddings:
        cached_texts, message_embeddings, cached_token_sets = cached_embeddings
        logger.info("Telegram semantic cache hit: messages=%s", len(cached_texts))
    else:
        cached_texts = texts
        cached_token_sets = [set(preprocess_text(m)) for m in cached_texts]

        model_name = getattr(settings, "embedding_model_name", "") or ""
        use_e5_prefix = "e5" in model_name.lower()
        passages = [f"passage: {m}" if use_e5_prefix else m for m in cached_texts]
        embed_started = perf_counter()
        message_embeddings = model.encode(passages, convert_to_tensor=True, normalize_embeddings=True)
        _semantic_cache_set(messages_key, (cached_texts, message_embeddings, cached_token_sets))
        logger.info(
            "Telegram semantic cache miss: embedded_messages=%s, elapsed_ms=%s",
            len(cached_texts),
            round((perf_counter() - embed_started) * 1000),
        )

    query_tokens = set(preprocess_text(clean_query))
    model_name = getattr(settings, "embedding_model_name", "") or ""
    use_e5_prefix = "e5" in model_name.lower()
    query_text = f"query: {clean_query}" if use_e5_prefix else clean_query
    query_embedding = model.encode([query_text], convert_to_tensor=True, normalize_embeddings=True)
    sims = util.cos_sim(query_embedding, message_embeddings)[0]

    # Сообщения ранжируем, потом агрегируем по пользователям.
    message_hits: list[dict] = []
    for local_idx, cos_score in enumerate(sims.tolist()):
        cos_value = float(cos_score)
        tokens = cached_token_sets[local_idx] if local_idx < len(cached_token_sets) else set()
        denom = max(len(query_tokens | tokens), 1)
        jaccard = (len(query_tokens & tokens) / denom) if query_tokens else 0.0
        score = 0.88 * cos_value + 0.12 * jaccard
        if score < floor:
            continue
        message_hits.append(
            {
                "userId": user_ids[local_idx],
                "name": user_names[local_idx],
                "message": cached_texts[local_idx],
                "score": float(score),
                "messageIndex": int(message_indices[local_idx]) if local_idx < len(message_indices) else int(local_idx),
            }
        )

    message_hits.sort(key=lambda x: x["score"], reverse=True)

    users: dict[str, dict] = {}
    for hit in message_hits:
        uid = hit["userId"]
        entry = users.get(uid)
        if not entry:
            entry = {"userId": uid, "name": hit["name"], "score": hit["score"], "matches": []}
            users[uid] = entry
        entry["score"] = max(float(entry["score"]), float(hit["score"]))
        if len(entry["matches"]) < limit_per_user:
            entry["matches"].append(
                {
                    "message": hit["message"],
                    "score": round(float(hit["score"]), 4),
                    "messageIndex": hit["messageIndex"],
                }
            )

    results = sorted(users.values(), key=lambda x: x["score"], reverse=True)[:limit_users]
    # Подправим формат score
    for r in results:
        r["score"] = round(float(r["score"]), 4)
    logger.info("Telegram semantic search finished: users=%s, elapsed_ms=%s", len(results), round((perf_counter() - started) * 1000))
    return results


# ---------------------------------------------------------------------------
# Речевые паттерны
# ---------------------------------------------------------------------------

def _extract_patterns(processed_messages: list[list[str]]) -> list[SpeechPatternScore]:
    transactions = []
    max_messages = min(len(processed_messages), settings.max_messages_for_patterns, 600)
    term_counts = Counter(
        word
        for msg in processed_messages[:max_messages]
        for word in set(msg)
        if not _is_noise_lemma(word)
    )
    allowed_terms = {
        word
        for word, _count in term_counts.most_common(80)
    }
    for msg in processed_messages[:max_messages]:
        terms = sorted({word for word in msg if word in allowed_terms})
        if len(terms) >= 2:
            transactions.append(terms[:10])

    if len(transactions) < settings.min_pattern_messages:
        return []

    try:
        pair_counts = Counter()
        antecedent_counts = Counter()
        for terms in transactions:
            for idx, antecedent in enumerate(terms):
                antecedent_counts[antecedent] += 1
                for consequent in terms[idx + 1:]:
                    pair_counts[(antecedent, consequent)] += 1

        min_pair_count = max(2, round(len(transactions) * settings.pattern_min_support))
        scored_pairs = []
        for (antecedent, consequent), count in pair_counts.items():
            confidence = count / max(antecedent_counts.get(antecedent, 1), 1)
            if count >= min_pair_count and confidence >= settings.pattern_min_confidence:
                scored_pairs.append((antecedent, consequent, confidence, count))

        scored_pairs.sort(key=lambda item: (item[2], item[3]), reverse=True)
        patterns = []
        for antecedent, consequent, confidence, _count in scored_pairs[:5]:
            if antecedent != consequent:
                patterns.append(
                    SpeechPatternScore(
                        pattern=f"Связка: '{antecedent}' + '{consequent}'",
                        confidence=round(float(confidence), 2),
                    )
                )
        return patterns
    except Exception:
        # Добавлено логирование ошибки
        logger.exception("Speech patterns extraction failed")
        return []


# ---------------------------------------------------------------------------
# Демография и стиль коммуникации
# ---------------------------------------------------------------------------


# Глобальная переменная для кэширования модели в оперативной памяти
_ZERO_SHOT_CLASSIFIER = None

def get_zero_shot_classifier():
    """Ленивая загрузка RuBERT-tiny для Zero-Shot классификации."""
    global _ZERO_SHOT_CLASSIFIER
    if _ZERO_SHOT_CLASSIFIER is None:
        logger.info("Загрузка модели rubert-tiny-bilingual-nli...")
        try:
            # device=-1 означает использование CPU. 
            # Если на сервере есть GPU (NVIDIA) и установлен CUDA, поменяйте на device=0
            _ZERO_SHOT_CLASSIFIER = pipeline(
                "zero-shot-classification",
                model="cointegrated/rubert-tiny-bilingual-nli",
                device=-1 
            )
            logger.info("Модель rubert-tiny-bilingual-nli успешно загружена.")
        except Exception as e:
            logger.error(f"Ошибка при загрузке Zero-Shot модели: {e}")
            return None
    return _ZERO_SHOT_CLASSIFIER



def _detect_age_by_rubert(messages: list[str]) -> tuple[str, float]:
    """Определение возраста пользователя: безопасные эвристики + Zero-Shot NLI."""
    if not messages:
        return "Не определен", 0.0

    full_text = " ".join(messages)

    # 1. БЕЗОПАСНАЯ ЭВРИСТИКА (Только явные фразы от первого лица)
    
    # Ищем фразы "мне 16", "мне 22 года" (с границами слов, чтобы не вырвать из контекста)
    age_match = re.search(r'(?i)(?:^|\s)мне\s+(?:уже\s+|исполнилось\s+)?(\d{1,2})(?:\s+(?:лет|год|года))?(?:\s|[.,!?]|$)', full_text)
    if age_match:
        try:
            age_num = int(age_match.group(1))
            if 7 < age_num < 100:  # Игнорируем странные цифры
                if age_num < 18:
                    return "Подросток (до 18)", 0.95
                elif age_num <= 25:
                    return "Молодой (18-25)", 0.95
                elif age_num <= 45:
                    return "Взрослый (25-45)", 0.95
                else:
                    return "Старший (45+)", 0.95
        except ValueError:
            pass
            
    # Только однозначные фразы (никаких одиночных слов "класс", "школа" или "пара")
    teen_phrases = r'(?i)\b(я в \d{1,2} классе|перешел в \d{1,2} класс|мои одноклассники|наша училка|задали домашку)\b'
    if re.search(teen_phrases, full_text):
        return "Подросток (до 18)", 0.85

    student_phrases = r'(?i)\b(я на \d унике|мои одногруппники|пишу курсач|моя зачетка)\b'
    if re.search(student_phrases, full_text):
        return "Молодой (18-25)", 0.85

    # 2. ПОДГОТОВКА ТЕКСТА ДЛЯ НЕЙРОСЕТИ
    classifier = get_zero_shot_classifier()
    if not classifier:
        return "Не определен", 0.0

    # Набираем с конца целые сообщения (не режем слова)
    valid_messages = []
    current_len = 0
    for msg in reversed(messages):
        msg_clean = msg.strip()
        if not msg_clean:
            continue
        if current_len + len(msg_clean) > 1500:
            break
        valid_messages.insert(0, msg_clean)
        current_len += len(msg_clean) + 1

    text_block = " ".join(valid_messages)
    
    if not text_block:
        return "Не определен", 0.0

    # Используем более нейтральные термины, чтобы избежать ложных срабатываний
    candidate_labels = [
        "подросток", 
        "молодой студент", 
        "взрослый человек", 
        "пожилой человек"
    ]

    try:
        # 3. ИНФЕРЕНС ZERO-SHOT
        result = classifier(
            text_block, 
            candidate_labels, 
            hypothesis_template="Этот текст написал {}.",
            multi_label=False
        )

        labels = result["labels"]
        scores = result["scores"]
        
        best_label_raw = labels[0]
        confidence = float(scores[0])
        second_confidence = float(scores[1]) if len(scores) > 1 else 0.0

        age_map = {
            "подросток": "Подросток (до 18)",
            "молодой студент": "Молодой (18-25)",
            "взрослый человек": "Взрослый (25-45)",
            "пожилой человек": "Старший (45+)"
        }

        # Отсекаем, если модель угадывает (уверенность меньше 28% или разрыв между 1 и 2 местом мизерный)
        if confidence < 0.28 or (confidence - second_confidence < 0.05):
            return "Не определен", 0.0

        return age_map.get(best_label_raw, "Не определен"), round(confidence, 2)

    except Exception as e:
        logger.exception(f"Ошибка во время Zero-Shot классификации возраста: {e}")
        return "Не определен", 0.0

_TOXICITY_PIPELINE = None


def get_toxicity_pipeline():
    """Ленивая загрузка модели для анализа токсичности и стиля."""
    global _TOXICITY_PIPELINE
    if _TOXICITY_PIPELINE is None:
        logger.info("Загрузка модели rubert-tiny-toxicity...")
        try:
            # Модель возвращает вероятности для классов: 
            # 0: non-toxic, 1: insult, 2: obscenity, 3: threat, 4: dangerous
            _TOXICITY_PIPELINE = pipeline(
                "text-classification",
                model="cointegrated/rubert-tiny-toxicity",
                top_k=None, # Просим вернуть баллы по всем категориям сразу
                device=-1
            )
            logger.info("Модель rubert-tiny-toxicity загружена.")
        except Exception as e:
            logger.error(f"Не удалось загрузить модель токсичности: {e}")
    return _TOXICITY_PIPELINE


def _analyze_communication_style_detailed(messages: list[str], tonality: dict) -> tuple[str, float]:
    pipe = get_toxicity_pipeline()
    if not pipe or not messages:
        return "Нейтральный стиль общения.", 0.0

    # Берем срез последних сообщений для анализа стиля (макс 30)
    sample = messages[-30:]
    try:
        results = pipe(sample)
    except Exception:
        return "Сбалансированный стиль.", 0.5

    # Агрегируем оценки
    scores = {"non-toxic": 0.0, "insult": 0.0, "obscenity": 0.0, "threat": 0.0, "dangerous": 0.0}
    count = len(results)

    for res in results:
        for label_obj in res:
            label = label_obj["label"]
            scores[label] += label_obj["score"]

    # Вычисляем среднее
    avg_scores = {k: v / count for k, v in scores.items()}
    
    # Логика формирования описания стиля
    style_parts = []
    
    # 1. Проверка на токсичность (индикаторы неадекватности)
    toxic_level = 1.0 - avg_scores["non-toxic"]
    
    if avg_scores["obscenity"] > 0.2:
        style_parts.append("Часто использует ненормативную лексику.")
    if avg_scores["insult"] > 0.2:
        style_parts.append("Склонен к переходу на личности и оскорблениям.")
    if avg_scores["threat"] > 0.1:
        style_parts.append("В сообщениях могут проскальзывать скрытые или прямые угрозы.")

    # 2. Если токсичности нет, смотрим на тональность (из вашего старого кода)
    if not style_parts:
        if tonality["positive"] > 45:
            style_parts.append("Доброжелательный, вежливый и позитивный стиль.")
        elif tonality["negative"] > 35:
            style_parts.append("Скептичный, критикующий, но в рамках приличия.")
        else:
            style_parts.append("Спокойный, нейтральный и информативный стиль общения.")

    # 3. Добавим уверенность (confidence)
    # За уверенность возьмем вероятность доминирующего стиля
    confidence = round(max(avg_scores.values()), 2)
    
    return " ".join(style_parts), confidence


def _is_valid_interest(word: str) -> bool:
    """Проверяет через Zero-Shot, является ли слово реальным интересом."""
    classifier = get_model("age") # Используем уже загруженный rubert-tiny
    if not classifier:
        return True # Если модель не загружена, пропускаем всё

    # Гипотеза: "Это слово описывает хобби, интерес или сферу деятельности"
    labels = ["интерес или тема", "мусорное слово или сленг"]
    try:
        res = classifier(word, labels, hypothesis_template="Это слово — {}.", multi_label=False)
        # Если вероятность того, что это интерес, выше чем у мусора
        return res["labels"][0] == "интерес или тема" and res["scores"][0] > 0.6
    except:
        return True

_MODELS = {
    "nlp": None,
    "age": None,
    "qa": None,
    "ner": None,
    "emotion": None
}

def get_model(name):
    if name not in _MODELS:
        raise KeyError(f"Unknown model: {name}")
    if _MODELS[name] is None:
        logger.info(f"Загрузка модели: {name}...")
        try:
            if name == "nlp":
                _MODELS["nlp"] = spacy.load("ru_core_news_md")
            elif name == "age":
                _MODELS["age"] = pipeline("zero-shot-classification", model="cointegrated/rubert-tiny-bilingual-nli")
            elif name == "qa":
                _MODELS["qa"] = pipeline("question-answering", model="timpal0l/mdeberta-v3-base-squad2")
            elif name == "ner":
                _MODELS["ner"] = pipeline("ner", model="DeepPavlov/rubert-base-cased-conversational-ner", aggregation_strategy="simple")
        except Exception:
            logger.exception("Model load failed: %s", name)
            return None
    return _MODELS[name]

# --- 1. АВТОНОМНЫЕ ИНТЕРЕСЫ (SpaCy + Freq) ---

def _extract_interests_dynamic(messages: list[str]) -> list[InterestScore]:
    processed_messages = [preprocess_text(msg) for msg in messages[-settings.max_messages_for_clustering:]]
    signal_context = _build_profile_signal_context(messages, processed_messages)
    signal_results = _extract_interests_from_signal_context(signal_context)
    if signal_results and not all(_is_placeholder_interest(item) for item in signal_results):
        return signal_results

    nlp = get_model("nlp")
    if not nlp:
        return signal_results or [_unknown_interest()]

    docs = nlp.pipe(messages[-100:])
    
    candidates = []
    for doc in docs:
        for token in doc:
            lemma = token.lemma_.lower()
            if (token.pos_ in {"NOUN", "PROPN"} and 
                not token.is_stop and 
                not _is_noise_lemma(lemma) and
                len(lemma) > 3):
                candidates.append(token.lemma_.capitalize())

    if not candidates:
        return [InterestScore(name="Мало данных", confidence=0.0)]

    # 1. Берем самые частотные (например, топ-15)
    raw_top = Counter(candidates).most_common(15)
    
    # 2. Просим нейросеть "отфильтровать" этот список
    valid_interests = []
    total_msgs = max(len(messages), 1)

    for name, count in raw_top:
        # Проверяем слово нейросетью
        if _is_valid_interest(name):
            rel_freq = count / total_msgs
            conf = min(0.95, round(0.4 + rel_freq, 2))
            valid_interests.append(InterestScore(name=name, confidence=conf))
            
        # Ограничиваем итоговый список (топ-8)
        if len(valid_interests) >= 8:
            break

    if not valid_interests:
        return [InterestScore(name="Интересы не выражены", confidence=0.0)]

    return valid_interests

    
# --- 2. АВТОНОМНАЯ ЗАНЯТОСТЬ (QA + NER) ---

def _extract_occupation_smart(messages: list[str]) -> tuple[str, float]:
    # Если сообщений совсем мало, не мучаем модель
    if len(messages) < 5:
        return "Не определена (мало данных)", 0.0

    processed_messages = [preprocess_text(msg) for msg in messages[-settings.max_messages_for_clustering:]]
    signal_context = _build_profile_signal_context(messages, processed_messages)
    signal_occupation = _extract_occupation_from_signal_context(signal_context)
    if not _is_unknown_occupation(*signal_occupation):
        return signal_occupation

    return "Не определена (мало данных)", 0.0

# --- 3. ОПРЕДЕЛЕНИЕ ПОЛА (SpaCy Dependency) ---

def _detect_gender_smart(messages: list[str]) -> tuple[str, float]:
    nlp = get_model("nlp")
    if not nlp:
        return "Не определен", 0.0

    m_score, f_score = 0, 0
    
    for doc in nlp.pipe(messages[-200:]):
        for token in doc:
            if token.pos_ == "VERB" and "Number=Sing" in str(token.morph):
                # Проверяем, относится ли глагол к автору (подлежащее "я")
                is_author = any(t.lemma_ == "я" and t.dep_ == "nsubj" for t in token.children)
                
                gender = token.morph.get("Gender")
                weight = 3.0 if is_author else 0.5 # Вес выше, если есть местоимение "я"
                
                if "Masc" in gender: m_score += weight
                elif "Fem" in gender: f_score += weight

    total = m_score + f_score
    if total < 2: return "Не определен", 0.0
    
    if m_score > f_score:
        return "Мужской", round(m_score / total, 2)
    return "Женский", round(f_score / total, 2)

# --- 4. ВОЗРАСТ (RuBERT Zero-Shot) ---

def _extract_entities(messages: list[str]) -> dict[str, list[str]]:
    """Извлекает сущности (Организации, Места, Имена) через SpaCy."""
    nlp = get_model("nlp")
    if not nlp or not messages:
        return {"ORG": [], "PER": [], "LOC": []}

    # Объединяем сообщения для анализа
    full_text = " ".join(messages[-50:]) # Берем последние 50 сообщений
    doc = nlp(full_text)
    
    entities = {"ORG": set(), "PER": set(), "LOC": set()}
    
    # SpaCy по умолчанию помечает сущности в doc.ents
    for ent in doc.ents:
        # ent.label_ может быть: ORG (организация), PER (личность), LOC (место/GPE)
        if ent.label_ in entities:
            # Очищаем от мусора и добавляем
            clean_name = ent.text.strip().replace("##", "")
            if len(clean_name) > 2:
                entities[ent.label_].add(clean_name)

    return {k: list(v) for k, v in entities.items()}

_QA_PIPELINE = None

def get_qa_pipeline():
    global _QA_PIPELINE
    if _QA_PIPELINE is None:
        # Модель mDeBERTa — одна из лучших для русского языка в задачах вопрос-ответ
        _QA_PIPELINE = pipeline(
            "question-answering", 
            model="timpal0l/mdeberta-v3-base-squad2",
            device=-1
        )
    return _QA_PIPELINE


_EMOTION_LABEL_RU_MAP = {
    "joy": "радость",
    "happiness": "счастье",
    "sadness": "грусть",
    "anger": "гнев",
    "fear": "страх",
    "disgust": "отвращение",
    "surprise": "удивление",
    "no_emotion": "нейтральное",
}


def _normalize_emotion_label(label: str) -> str:
    l = str(label).strip().lower()
    l = re.sub(r"\s+", " ", l)
    return _EMOTION_LABEL_RU_MAP.get(l, l)
