from pydantic import BaseModel


class Settings(BaseModel):
    cors_origins: list[str] = ["*"]
    log_level: str = "INFO"

    # --- NLP модели ---
    emotion_model_name: str = "cointegrated/rubert-tiny2-cedr-emotion-detection"
    embedding_model_name: str = "google/embeddinggemma-300m"
    embedding_model_fallback_name: str = "intfloat/multilingual-e5-small"
    warmup_models_on_startup: bool = True

    # --- Эмоции / тональность ---
    emotion_sample_size: int = 150

    # --- Речевые паттерны ---
    max_messages_for_patterns: int = 1000
    min_pattern_messages: int = 5
    pattern_min_support: float = 0.03
    pattern_min_confidence: float = 0.4

    # --- Кластеризация интересов ---
    interest_n_clusters: int = 10
    min_cluster_size: int = 5
    max_messages_for_clustering: int = 1500
    cluster_top_keywords: int = 3  # сколько ключевых слов в метке кластера

    # --- Кэш ---
    analysis_cache_size: int = 64
    semantic_cache_size: int = 32
    semantic_max_messages: int = 1200


settings = Settings()
