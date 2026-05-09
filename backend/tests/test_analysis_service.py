import pytest

from app.schemas import InterestScore, SpeechPatternScore
from app.services import analysis


@pytest.fixture(autouse=True)
def clear_analysis_cache():
    analysis._cache.clear()
    analysis._semantic_embeddings_cache.clear()


def _stub_profile_dependencies(monkeypatch):
    monkeypatch.setattr(
        analysis,
        "_analyze_emotions",
        lambda msgs: ({"positive": 50, "neutral": 40, "negative": 10, "confidence": 0.5}, []),
    )
    monkeypatch.setattr(
        analysis,
        "_extract_keywords",
        lambda lemmas: [{"keyword": "код", "confidence": 1.0}, {"keyword": "тест", "confidence": 0.7}],
    )
    monkeypatch.setattr(
        analysis,
        "_extract_patterns",
        lambda processed: [SpeechPatternScore(pattern="Связка: 'код' + 'тест'", confidence=0.8)],
    )
    monkeypatch.setattr(analysis, "_detect_gender_smart", lambda msgs: ("Мужской", 0.8))
    monkeypatch.setattr(
        analysis,
        "_analyze_communication_style_detailed",
        lambda msgs, tonality: ("Спокойный стиль.", 0.7),
    )
    monkeypatch.setattr(analysis, "_detect_age_by_rubert", lambda msgs: ("Молодой (18-25)", 0.6))


def test_analyze_profile_uses_qa_local_detectors(monkeypatch):
    _stub_profile_dependencies(monkeypatch)
    monkeypatch.setattr(
        analysis,
        "_extract_interests_dynamic",
        lambda msgs: [
            InterestScore(name="Программирование", confidence=0.86),
            InterestScore(name="Тестирование", confidence=0.7),
        ],
    )
    monkeypatch.setattr(
        analysis,
        "_extract_occupation_smart",
        lambda msgs: ("Разработчик", 0.75),
    )

    result = analysis.analyze_profile("alex", ["Я писал код", "Я люблю тесты"])

    assert result.username == "alex"
    assert [k.keyword for k in result.nlpAnalysis.keywords] == ["код", "тест"]
    assert [i.name for i in result.topicsAndInterests] == ["Программирование", "Тестирование"]
    assert [i.confidence for i in result.topicsAndInterests] == [0.86, 0.7]
    assert result.demographics.occupation == "Разработчик"
    assert result.demographics.occupationConfidence == 0.75
    assert result.meta.usedCache is False


def test_analyze_profile_clamps_detector_confidence(monkeypatch):
    _stub_profile_dependencies(monkeypatch)
    monkeypatch.setattr(
        analysis,
        "_extract_interests_dynamic",
        lambda msgs: [InterestScore(name="Программирование", confidence=0.9)],
    )
    monkeypatch.setattr(
        analysis,
        "_extract_occupation_smart",
        lambda msgs: ("QA-инженер", 1.36),
    )

    result = analysis.analyze_profile("alex", ["Я писал код", "Я люблю тесты"])

    assert result.demographics.occupation == "QA-инженер"
    assert result.demographics.occupationConfidence == 1.0


def test_analyze_profile_uses_cache(monkeypatch):
    _stub_profile_dependencies(monkeypatch)
    monkeypatch.setattr(
        analysis,
        "_extract_interests_dynamic",
        lambda msgs: [InterestScore(name="Программирование", confidence=0.9)],
    )
    monkeypatch.setattr(analysis, "_extract_occupation_smart", lambda msgs: ("Разработчик", 0.75))

    first = analysis.analyze_profile("alex", ["Я писал код"])
    second = analysis.analyze_profile("alex", ["Я писал код"])

    assert first.meta.usedCache is False
    assert second.meta.usedCache is True


def test_model_loader_returns_none_on_load_error(monkeypatch):
    analysis._MODELS["nlp"] = None
    monkeypatch.setattr(analysis.spacy, "load", lambda name: (_ for _ in ()).throw(RuntimeError("missing model")))

    assert analysis.get_model("nlp") is None
