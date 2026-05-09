import logging
from functools import lru_cache

from sentence_transformers import SentenceTransformer, util
from transformers import pipeline

from app.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_emotion_pipeline():
    try:
        logger.info("Loading emotion model: %s", settings.emotion_model_name)
        return pipeline(
            "text-classification",
            model=settings.emotion_model_name,
            top_k=None,
        )
    except Exception:
        logger.exception("Не удалось загрузить emotion модель")
        return None


@lru_cache(maxsize=1)
def get_embedding_model():
    try:
        logger.info("Loading embedding model: %s", settings.embedding_model_name)
        return SentenceTransformer(settings.embedding_model_name)
    except Exception:
        logger.exception("Не удалось загрузить embedding модель '%s'", settings.embedding_model_name)
        logger.info("Loading embedding fallback model: %s", settings.embedding_model_fallback_name)
        return SentenceTransformer(settings.embedding_model_fallback_name)


def cosine_similarity(a, b) -> float:
    return float(util.cos_sim(a, b).item())
