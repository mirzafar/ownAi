"""Модели данных. После рефакторинга на единую коллекцию `analyses` —
звонки, лиды и чаты представлены одной структурой `AnalysisDoc`, отличаясь
только полем `kind` и блоком `call`/`lead`/`chat` со специфичными данными.
"""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════════
# Auth
# ═══════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════
# Scoring (общая структура оценки для звонка, чата, лида)
# ═══════════════════════════════════════════════════════════════════════════

class CriterionScore(BaseModel):
    id: str                  # machine id из scoring_card
    name: str                # человекочитаемое имя
    category_id: str
    category_name: str
    score: int               # 0..max
    max_score: int
    comment: str = ""


class StopFactor(BaseModel):
    id: str
    name: str
    penalty: int             # положительное число — на сколько вычесть
    triggered: bool = False
    comment: str = ""


class CoachingTask(BaseModel):
    title: str
    focus_area: str
    action_item: str


class ScoringMeta(BaseModel):
    verdict: str = ""
    raw_score: int = 0           # -max_penalty..max_raw_score (исходя из карты)
    max_raw_score: int = 0       # snapshot карты на момент анализа
    normalized_score: int = 0    # 0..100
    grade: str = ""              # Эталон / Хороший / Удовлетворительно / Неудовлетворительно


class Scoring(BaseModel):
    """Унифицированная оценка по карте Swiss Collection."""
    meta: ScoringMeta
    strengths: List[str] = []
    weaknesses: List[str] = []
    criteria_scores: List[CriterionScore] = []
    stop_factors: List[StopFactor] = []
    coaching_tasks: List[CoachingTask] = []
    # Доп. атрибуты звонка/чата
    sentiment: str = ""          # positive | neutral | negative | mixed | ""
    topics: List[str] = []
    summary: str = ""            # короткое резюме (для звонка/чата)


# ═══════════════════════════════════════════════════════════════════════════
# Kind-специфичные подблоки
# ═══════════════════════════════════════════════════════════════════════════

class CallData(BaseModel):
    bitrix_call_id: str = ""
    phone: str = ""
    direction: str = ""              # Входящий / Исходящий
    record_url: str = ""
    has_audio: bool = False
    language: str = ""


class ChatData(BaseModel):
    bitrix_chat_id: str = ""
    channel: str = ""                # WhatsApp / Telegram / ...
    client: str = ""
    subject: str = ""
    messages_count: int = 0


class LeadCallRef(BaseModel):
    """Ссылка на отдельный звонок, использованный в анализе лида."""
    analysis_id: str = ""            # id записи kind=call в analyses
    call_id: str = ""                # bitrix_call_id
    date: Optional[datetime] = None
    direction: str = ""
    duration: int = 0
    normalized_score: int = 0
    grade: str = ""
    analyzed: bool = False
    skipped_reason: str = ""         # "" | no_record | too_large | failed:...


class LeadData(BaseModel):
    bitrix_lead_id: str = ""
    title: str = ""
    status_id: str = ""
    status_name: str = ""
    source_id: str = ""
    source_name: str = ""
    opportunity: float = 0.0
    currency: str = ""
    bitrix_url: str = ""
    # Качественная сводка по лиду
    summary: str = ""
    client_request: str = ""
    objections: List[str] = []
    risk: str = "low"                # low | medium | high
    risk_reason: str = ""
    next_step: str = ""
    calls_count: int = 0
    comments_count: int = 0
    call_refs: List[LeadCallRef] = []
    input_hash: str = ""             # кэш-ключ агрегированного анализа


# ═══════════════════════════════════════════════════════════════════════════
# Главная модель — запись в коллекции `analyses`
# ═══════════════════════════════════════════════════════════════════════════

AnalysisKind = Literal["call", "chat", "lead"]
AnalysisStatus = Literal["processing", "done", "failed"]


class AnalysisOut(BaseModel):
    """То, что отдаёт API клиенту."""
    id: str
    kind: AnalysisKind
    status: AnalysisStatus
    title: str = ""                  # display name (filename / lead title)
    date: Optional[datetime] = None  # для сортировки и dashboard (call_date / lead.created)
    duration: int = 0                # секунды (для звонка)
    manager: str = ""
    manager_id: str = ""
    source_text: str = ""            # транскрипт / агрегат текстов лида
    scoring: Optional[Scoring] = None
    call: Optional[CallData] = None
    chat: Optional[ChatData] = None
    lead: Optional[LeadData] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    error: str = ""


# ═══════════════════════════════════════════════════════════════════════════
# Аналитика (общая по всем kind)
# ═══════════════════════════════════════════════════════════════════════════

class OperatorStat(BaseModel):
    manager_id: str
    manager: str
    total: int = 0                   # суммарно записей (звонки+лиды+чаты или фильтр)
    calls: int = 0
    leads: int = 0
    chats: int = 0
    analyzed: int = 0
    avg_score: Optional[float] = None
    total_duration: int = 0
    last_activity_at: Optional[datetime] = None


class OperatorDailyStat(BaseModel):
    date: str                        # YYYY-MM-DD
    total: int
    calls: int = 0
    leads: int = 0
    chats: int = 0
    avg_score: Optional[float] = None
    total_duration: int = 0


class OperatorDetail(BaseModel):
    manager_id: str
    manager: str
    period_days: int
    stats: OperatorStat
    daily: List[OperatorDailyStat] = []
    analyses: List[AnalysisOut] = []


class CriterionAverage(BaseModel):
    id: str
    name: str
    category_id: str = ""
    category_name: str = ""
    avg_score: float
    max_score: int
    samples: int


class KindCount(BaseModel):
    calls: int = 0
    leads: int = 0
    chats: int = 0


class DailyPoint(BaseModel):
    date: str
    total: int = 0
    calls: int = 0
    leads: int = 0
    chats: int = 0
    avg_score: Optional[float] = None


class AnalyticsOverview(BaseModel):
    total: int = 0
    analyzed: int = 0
    by_kind: KindCount = Field(default_factory=KindCount)
    avg_score: Optional[float] = None
    total_duration: int = 0
    sentiment_breakdown: dict = {}
    grade_breakdown: dict = {}      # "Эталон": N, "Хороший": N, ...
    criteria: List[CriterionAverage] = []
    operators: List[OperatorStat] = []
    daily: List[DailyPoint] = []


# ═══════════════════════════════════════════════════════════════════════════
# Bitrix-DTO (то, что отдаём для UI «Звонки» / «Лиды» — без анализа)
# ═══════════════════════════════════════════════════════════════════════════

class BitrixCall(BaseModel):
    id: str
    phone: str = ""
    date: Optional[datetime] = None
    duration: int = 0
    direction: str = ""
    manager: str = ""
    manager_id: str = ""
    record_url: str = ""
    analysis_id: Optional[str] = None  # id записи в analyses
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
    analysis_id: Optional[str] = None
    analyzed: bool = False


class BitrixChatsPage(BaseModel):
    items: List[BitrixChat]
    total: int
    page: int
    page_size: int


class BitrixLeadStatus(BaseModel):
    status_id: str
    name: str
    sort: int = 0
    color: str = ""


class BitrixLead(BaseModel):
    id: str
    title: str = ""
    name: str = ""
    last_name: str = ""
    second_name: str = ""
    status_id: str = ""
    status_name: str = ""
    source_id: str = ""
    source_name: str = ""
    opportunity: float = 0.0
    currency_id: str = ""
    phone: str = ""
    email: str = ""
    assigned_by_id: str = ""
    assigned_by: str = ""
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    # Доп. инфо о текущем анализе (если уже считался)
    analysis_id: Optional[str] = None
    analysis_status: str = ""
    analysis_score: int = 0          # normalized 0..100
    analysis_risk: str = ""


class BitrixLeadsPage(BaseModel):
    items: List[BitrixLead]
    total: int
    page: int
    page_size: int


class BitrixContactValue(BaseModel):
    value: str
    kind: str = ""


class BitrixLeadDetail(BaseModel):
    id: str
    bitrix_url: str = ""
    title: str = ""
    name: str = ""
    last_name: str = ""
    second_name: str = ""
    honorific: str = ""
    status_id: str = ""
    status_name: str = ""
    source_id: str = ""
    source_description: str = ""
    opportunity: float = 0.0
    currency_id: str = ""
    assigned_by_id: str = ""
    assigned_by: str = ""
    created_by_id: str = ""
    created_by: str = ""
    company_title: str = ""
    post: str = ""
    address: str = ""
    comments: str = ""
    phones: List[BitrixContactValue] = []
    emails: List[BitrixContactValue] = []
    webs: List[BitrixContactValue] = []
    ims: List[BitrixContactValue] = []
    utm_source: str = ""
    utm_medium: str = ""
    utm_campaign: str = ""
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None


class BitrixLeadTimelineEntry(BaseModel):
    id: str
    kind: str                        # comment | activity
    activity_type: str = ""
    subject: str = ""
    text: str = ""
    author_id: str = ""
    author: str = ""
    completed: bool = False
    direction: str = ""
    date: Optional[datetime] = None


class BitrixLeadActivity(BaseModel):
    timeline: List[BitrixLeadTimelineEntry] = []
    calls: List[BitrixCall] = []
