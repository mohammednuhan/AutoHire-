from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base
from app.db.enums import ApplicationStatus, AuditEventType, DecisionReason, JobSource


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UserProfile(Base, TimestampMixin):
    __tablename__ = "user_profiles"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    phone: Mapped[str | None] = mapped_column(String(32))
    location: Mapped[str | None] = mapped_column(String(160))
    education: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    skills: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    links: Mapped[dict[str, str]] = mapped_column(JSONB, default=dict, nullable=False)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    resumes: Mapped[list[Resume]] = relationship(back_populates="user_profile")


class Resume(Base, TimestampMixin):
    __tablename__ = "resumes"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    user_profile_id: Mapped[str] = mapped_column(ForeignKey("user_profiles.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    format: Mapped[str] = mapped_column(String(64), default="single_column_text", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    user_profile: Mapped[UserProfile] = relationship(back_populates="resumes")


class Company(Base, TimestampMixin):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    website: Mapped[str | None] = mapped_column(String(500))
    is_dream_company: Mapped[bool] = mapped_column(default=False, nullable=False)

    jobs: Mapped[list[JobPosting]] = relationship(back_populates="company")


class JobPosting(Base, TimestampMixin):
    __tablename__ = "job_postings"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_job_posting_source_external_id"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id"))
    source: Mapped[JobSource] = mapped_column(Enum(JobSource, name="job_source"), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    required_skills: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    company: Mapped[Company | None] = relationship(back_populates="jobs")
    application: Mapped[Application | None] = relationship(back_populates="job_posting")


class Application(Base, TimestampMixin):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    job_posting_id: Mapped[str] = mapped_column(ForeignKey("job_postings.id"), nullable=False, unique=True)
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus, name="application_status"),
        default=ApplicationStatus.DISCOVERED,
        nullable=False,
    )
    score: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float | None] = mapped_column(Numeric(3, 2))
    decision_reason: Mapped[DecisionReason | None] = mapped_column(
        Enum(DecisionReason, name="decision_reason"),
    )
    daily_cap_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    job_posting: Mapped[JobPosting] = relationship(back_populates="application")
    audit_events: Mapped[list[AuditEvent]] = relationship(back_populates="application")


class CoverLetter(Base, TimestampMixin):
    __tablename__ = "cover_letters"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), nullable=False, unique=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    paragraph_count: Mapped[int] = mapped_column(Integer, nullable=False)
    model_provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model_name: Mapped[str] = mapped_column(String(160), nullable=False)


class ScreeningAnswer(Base, TimestampMixin):
    __tablename__ = "screening_answers"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)
    model_provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model_name: Mapped[str] = mapped_column(String(160), nullable=False)


class ScreenshotAudit(Base, TimestampMixin):
    __tablename__ = "screenshot_audits"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    application_id: Mapped[str | None] = mapped_column(ForeignKey("applications.id"))
    field_name: Mapped[str | None] = mapped_column(String(160))
    path: Mapped[str] = mapped_column(String(1000), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)


class AuditEvent(Base, TimestampMixin):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    application_id: Mapped[str | None] = mapped_column(ForeignKey("applications.id"))
    event_type: Mapped[AuditEventType] = mapped_column(Enum(AuditEventType, name="audit_event_type"))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    application: Mapped[Application | None] = relationship(back_populates="audit_events")
