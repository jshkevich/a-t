from fastapi import APIRouter

from app.importer.telegram_export import get_participants, get_user_messages, get_username
from app.schemas import (
    ProfileAnalysisResponse,
    SemanticSearchRequest,
    SemanticSearchResponse,
    TelegramSemanticSearchRequest,
    TelegramSemanticSearchResponse,
    TelegramAnalyzeRequest,
    TelegramParticipantsResponse,
    TelegramParticipant,
    TelegramExport,
    UserMessages,
)
from app.services.analysis import analyze_profile, semantic_search_chat, semantic_search_messages

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/analyze", response_model=ProfileAnalysisResponse)
async def analyze(data: UserMessages):
    return analyze_profile(data.username, data.messages)


@router.post("/semantic-search", response_model=SemanticSearchResponse)
async def semantic_search(data: SemanticSearchRequest):
    results = semantic_search_messages(
        query=data.query,
        messages=data.messages,
        top_k=data.topK,
        min_score=data.minScore,
    )
    return SemanticSearchResponse(results=results)


@router.post("/telegram/participants", response_model=TelegramParticipantsResponse)
async def telegram_participants(chat: TelegramExport):
    participants = [TelegramParticipant(**p) for p in get_participants(chat.model_dump())]
    return TelegramParticipantsResponse(participants=participants)


@router.post("/telegram/analyze", response_model=ProfileAnalysisResponse)
async def telegram_analyze(data: TelegramAnalyzeRequest):
    chat_dict = data.chat.model_dump()
    msgs = get_user_messages(chat_dict, data.userId)
    username = data.username or get_username(chat_dict, data.userId) or f"user:{data.userId}"
    return analyze_profile(username, msgs)


@router.post("/telegram/semantic-search", response_model=TelegramSemanticSearchResponse)
async def telegram_semantic_search(data: TelegramSemanticSearchRequest):
    results = semantic_search_chat(
        chat=data.chat.model_dump(),
        query=data.query,
        top_users=data.topUsers,
        per_user_k=data.perUserK,
        min_score=data.minScore,
    )
    return TelegramSemanticSearchResponse(results=results)

