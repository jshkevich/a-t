from pydantic import BaseModel, Field


class UserMessages(BaseModel):
    username: str
    messages: list[str]


class TelegramExport(BaseModel):
    """Telegram Desktop export JSON (мы не жёстко валидируем структуру целиком)."""

    messages: list[dict] = Field(default_factory=list)


class TelegramParticipant(BaseModel):
    id: str
    name: str
    messageCount: int = Field(ge=0, default=0)


class TelegramParticipantsResponse(BaseModel):
    participants: list[TelegramParticipant]


class TelegramAnalyzeRequest(BaseModel):
    chat: TelegramExport
    userId: str
    username: str | None = None


class SemanticSearchRequest(BaseModel):
    query: str
    messages: list[str]
    topK: int = Field(default=5, ge=1, le=20)
    minScore: float = Field(default=0.2, ge=0.0, le=1.0)


class SemanticSearchItem(BaseModel):
    message: str
    score: float = Field(ge=0.0, le=1.0)
    index: int = Field(ge=0)


class SemanticSearchResponse(BaseModel):
    results: list[SemanticSearchItem]


class TelegramSemanticSearchRequest(BaseModel):
    chat: TelegramExport
    query: str
    topUsers: int = Field(default=5, ge=1, le=20)
    perUserK: int = Field(default=2, ge=1, le=5)
    minScore: float = Field(default=0.25, ge=0.0, le=1.0)


class TelegramSemanticMatch(BaseModel):
    message: str
    score: float = Field(ge=0.0, le=1.0)
    messageIndex: int = Field(ge=0)


class TelegramSemanticUserHit(BaseModel):
    userId: str
    name: str
    score: float = Field(ge=0.0, le=1.0)
    matches: list[TelegramSemanticMatch]


class TelegramSemanticSearchResponse(BaseModel):
    results: list[TelegramSemanticUserHit]


class Demographics(BaseModel):
    age: str
    ageConfidence: float = Field(ge=0.0, le=1.0, default=0.0)
    gender: str
    genderConfidence: float = Field(ge=0.0, le=1.0, default=0.0)
    occupation: str
    occupationConfidence: float = Field(ge=0.0, le=1.0, default=0.0)


class Tonality(BaseModel):
    positive: int = Field(ge=0, le=100)
    neutral: int = Field(ge=0, le=100)
    negative: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class EmotionScore(BaseModel):
    label: str
    percentage: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class InterestScore(BaseModel):
    name: str
    confidence: float = Field(ge=0.0, le=1.0)


class KeywordScore(BaseModel):
    keyword: str
    confidence: float = Field(ge=0.0, le=1.0)


class SpeechPatternScore(BaseModel):
    pattern: str
    confidence: float = Field(ge=0.0, le=1.0)


class NlpAnalysis(BaseModel):
    tonality: Tonality
    emotions: list[EmotionScore]
    communicationStyle: str
    communicationStyleConfidence: float = Field(ge=0.0, le=1.0, default=0.0)
    speechPatterns: list[SpeechPatternScore]
    keywords: list[KeywordScore]


class AnalysisMeta(BaseModel):
    usedCache: bool
    processedMessages: int
    messagesUsedForPatterns: int
    messagesUsedForInterests: int
    sentimentSampleSize: int
    language: str = "unknown"
    languageConfidence: float = Field(ge=0.0, le=1.0, default=0.0)


class ProfileAnalysisResponse(BaseModel):
    username: str
    demographics: Demographics
    topicsAndInterests: list[InterestScore]
    nlpAnalysis: NlpAnalysis
    meta: AnalysisMeta
