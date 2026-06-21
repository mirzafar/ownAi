from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


class UserRegister(BaseModel):
    login: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=6, max_length=128)
    name: str = Field(min_length=1, max_length=80)


class UserLogin(BaseModel):
    login: str
    password: str


class UserOut(BaseModel):
    id: str
    login: str
    name: str
    phone: str = ""
    email: str = ""
    address: str = ""
    is_admin: bool = False


class UserProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    phone: Optional[str] = Field(default=None, max_length=40)
    email: Optional[str] = Field(default=None, max_length=120)
    address: Optional[str] = Field(default=None, max_length=200)


class PasswordReset(BaseModel):
    new_password: str = Field(min_length=6, max_length=128)


class UserCreate(BaseModel):
    login: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=6, max_length=128)
    name: str = Field(min_length=1, max_length=80)
    phone: str = ""
    email: str = ""
    address: str = ""
    is_admin: bool = False


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class AnalysisResult(BaseModel):
    summary: str
    topics: List[str] = []
    sentiment: str = ""
    action_items: List[str] = []
    language: str = ""


class CriterionScore(BaseModel):
    criterion_id: str
    criterion_name: str
    score: int
    comment: str = ""


class CoachingTask(BaseModel):
    title: str
    focus_area: str
    action_item: str


class SalesAnalysisMeta(BaseModel):
    system_verdict: str
    total_score: int


class SalesAnalysisBlock(BaseModel):
    strengths: List[str] = []
    weaknesses: List[str] = []


class SalesAnalysis(BaseModel):
    meta: SalesAnalysisMeta
    analysis: SalesAnalysisBlock
    criteria_scores: List[CriterionScore] = []
    ai_coaching_tasks: List[CoachingTask] = []


class TranscriptionOut(BaseModel):
    id: str
    filename: str
    duration: Optional[float] = None
    text: str
    analysis: Optional[AnalysisResult] = None
    sales_analysis: Optional[SalesAnalysis] = None
    source: Optional[str] = None
    bitrix_call_id: Optional[str] = None
    bitrix_chat_id: Optional[str] = None
    bitrix_manager: str = ""
    bitrix_manager_id: str = ""
    bitrix_phone: str = ""
    bitrix_direction: str = ""
    bitrix_channel: str = ""
    bitrix_client: str = ""
    bitrix_call_date: Optional[datetime] = None
    messages_count: int = 0
    has_audio: bool = False
    status: str
    created_at: datetime
    error: Optional[str] = None


class OperatorStat(BaseModel):
    manager_id: str
    manager: str
    calls: int
    analyzed: int
    avg_score: Optional[float] = None
    total_duration: int = 0
    last_call_at: Optional[datetime] = None


class CriterionAverage(BaseModel):
    criterion_id: str
    criterion_name: str
    avg_score: float
    samples: int


class AnalyticsOverview(BaseModel):
    total_calls: int
    analyzed: int
    avg_score: Optional[float] = None
    total_duration: int = 0
    sentiment_breakdown: dict = {}
    criteria: List[CriterionAverage] = []
    operators: List[OperatorStat] = []
    daily: List[dict] = []


class BitrixCall(BaseModel):
    id: str
    phone: str = ""
    date: Optional[datetime] = None
    duration: int = 0
    direction: str = ""
    manager: str = ""
    manager_id: str = ""
    record_url: str = ""
    transcription_id: Optional[str] = None
    analyzed: bool = False


class BitrixCallsPage(BaseModel):
    items: List[BitrixCall]
    total: int
    page: int
    page_size: int


class BitrixChat(BaseModel):
    id: str
    subject: str = ""
    channel: str = ""
    client: str = ""
    operator: str = ""
    operator_id: str = ""
    started_at: Optional[datetime] = None
    messages_count: int = 0
    transcription_id: Optional[str] = None
    analyzed: bool = False


class BitrixChatsPage(BaseModel):
    items: List[BitrixChat]
    total: int
    page: int
    page_size: int
