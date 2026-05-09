import logging
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import settings
from app.nlp.models import get_embedding_model, get_emotion_pipeline

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Backend startup initiated")
    if settings.warmup_models_on_startup:
        started = perf_counter()
        logger.info("Model warmup started (emotion + embedding)")
        emotion_pipe = get_emotion_pipeline()
        if emotion_pipe:
            logger.info("Emotion model warmup OK")
        else:
            logger.warning("Emotion model warmup skipped/fallback")
        embedding_model = get_embedding_model()
        try:
            embedding_model.encode(["warmup"], normalize_embeddings=True)
            logger.info("Embedding model warmup OK")
        except Exception:
            logger.exception("Embedding model warmup failed")
        elapsed_ms = round((perf_counter() - started) * 1000)
        logger.info("Model warmup finished in %sms", elapsed_ms)
    else:
        logger.info("Model warmup disabled by config")
    yield
    logger.info("Backend shutdown complete")


app = FastAPI(title="Telegram Semantic Profiler API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

