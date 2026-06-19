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


class TranscriptionOut(BaseModel):
    id: str
    filename: str
    duration: Optional[float] = None
    text: str
    analysis: Optional[AnalysisResult] = None
    status: str
    created_at: datetime
    error: Optional[str] = None
