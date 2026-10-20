"""
Модели SQLAlchemy 2.x для HH AutoApply.
Соответствуют схеме из AGENTS.md.
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Integer, Boolean, DateTime, ForeignKey, JSON, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class User(Base):
    """Пользователь системы."""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_pw = Column(Text, nullable=False)
    hh_login = Column(String(255))
    hh_password = Column(Text)
    resume_id = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    settings = relationship("Settings", back_populates="user", uselist=False, cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="user", cascade="all, delete-orphan")
    applies = relationship("Apply", back_populates="user", cascade="all, delete-orphan")


class Settings(Base):
    """Настройки пользователя."""
    __tablename__ = "settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    cover_letter = Column(Text, default="")
    delay_min = Column(Integer, default=1)
    delay_max = Column(Integer, default=3)
    rate_limit = Column(Integer, default=20)
    headless = Column(Boolean, default=True)

    user = relationship("User", back_populates="settings")


class Job(Base):
    """Задача на отклик."""
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    mode = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False, default="pending")
    filters = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="jobs")
    applies = relationship("Apply", back_populates="job", cascade="all, delete-orphan")


class Apply(Base):
    """Результат отклика на вакансию."""
    __tablename__ = "applies"
    __table_args__ = (
        UniqueConstraint("user_id", "vacancy_id", name="uq_applies_user_vacancy"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    vacancy_id = Column(String(100), nullable=False)
    vacancy_url = Column(Text, nullable=False)
    vacancy_title = Column(String(500), nullable=False)
    company = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False)
    error_msg = Column(Text, nullable=True)
    applied_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    job = relationship("Job", back_populates="applies")
    user = relationship("User", back_populates="applies")
