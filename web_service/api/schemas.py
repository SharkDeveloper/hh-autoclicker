"""
Pydantic схемы для запросов и ответов API.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, validator
import uuid


# Auth schemas
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    hh_login: Optional[str] = None
    resume_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# Settings schemas
class SettingsBase(BaseModel):
    hh_login: Optional[str] = None
    hh_password: Optional[str] = None  # Открытый пароль (будет зашифрован)
    resume_id: Optional[str] = None
    cover_letter: Optional[str] = ""
    delay_min: int = Field(1, ge=1, le=10)
    delay_max: int = Field(3, ge=1, le=30)
    rate_limit: int = Field(20, ge=1, le=100)
    headless: bool = True


class SettingsResponse(SettingsBase):
    id: uuid.UUID
    user_id: uuid.UUID

    class Config:
        from_attributes = True


# Job schemas
class JobFilters(BaseModel):
    text: Optional[str] = None
    area: Optional[str] = None
    salary: Optional[int] = None
    experience: Optional[str] = None
    employment: Optional[List[str]] = None
    schedule: Optional[List[str]] = None


class JobCreate(BaseModel):
    mode: str = Field(..., pattern="^(auto|manual|recommendations)$")
    filters: Optional[JobFilters] = None
    vacancy_urls: Optional[List[str]] = None
    resume_id: Optional[str] = None  # Переопределение resume_id из настроек

    @validator("vacancy_urls")
    def validate_vacancy_urls(cls, v, values):
        if values.get("mode") == "manual" and (not v or len(v) == 0):
            raise ValueError("vacancy_urls обязателен для режима manual")
        return v


class JobResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    mode: str
    status: str
    filters: Optional[Dict[str, Any]] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    jobs: List[JobResponse]
    total: int
    page: int
    page_size: int


# Apply schemas
class ApplyResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    user_id: uuid.UUID
    vacancy_id: str
    vacancy_url: str
    vacancy_title: str
    company: str
    status: str
    error_msg: Optional[str] = None
    applied_at: datetime

    class Config:
        from_attributes = True


# Stats schemas
class StatsSummary(BaseModel):
    total_applies: int
    today_applies: int
    sent_count: int
    skipped_count: int
    error_count: int
    active_jobs: int


class StatsHistoryRequest(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[str] = None
    limit: int = 100
    offset: int = 0


class StatsHistoryResponse(BaseModel):
    applies: List[ApplyResponse]
    total: int


# Kafka message schemas (для внутреннего использования)
class KafkaJobMessage(BaseModel):
    job_id: uuid.UUID
    user_id: uuid.UUID
    mode: str
    hh_login: str
    hh_password_enc: str  # Зашифрованный пароль
    resume_id: Optional[str] = None
    cover_letter: Optional[str] = ""
    filters: Optional[Dict[str, Any]] = None
    rate_limit: int = 20
    delay_range: List[int] = [1, 3]
    vacancy_urls: List[str] = []


class KafkaResultMessage(BaseModel):
    job_id: uuid.UUID
    user_id: uuid.UUID
    status: str  # "done" | "failed"
    applies: List[Dict[str, Any]]
    total_sent: int
    total_skipped: int
    total_errors: int
    finished_at: datetime
    error: Optional[str] = None