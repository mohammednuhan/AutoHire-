from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(AsyncAttrs, DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, username={self.username!r})"


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    original_file_path: Mapped[str] = mapped_column(Text, nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text)
    profile_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    def __repr__(self) -> str:
        return f"Resume(id={self.id!r}, user_id={self.user_id!r}, filename={self.original_filename!r})"


class UserPreference(Base):
    __tablename__ = "user_preferences"
    __table_args__ = (
        CheckConstraint("score_threshold BETWEEN 50 AND 95", name="user_preferences_score_threshold_check"),
        CheckConstraint("max_apps_per_day BETWEEN 1 AND 30", name="user_preferences_max_apps_per_day_check"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    target_roles: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    preferred_locations: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    work_type: Mapped[str] = mapped_column(String(50), server_default=text("'any'"))
    salary_min_inr: Mapped[int | None] = mapped_column(Integer)
    salary_max_inr: Mapped[int | None] = mapped_column(Integer)
    experience_level: Mapped[str] = mapped_column(String(50), server_default=text("'entry'"))
    job_types: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("ARRAY['fulltime']"))
    industry_include: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    industry_exclude: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    blacklisted_companies: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    dream_companies: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    keyword_blacklist: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        server_default=text("ARRAY['10+ years','US citizenship required','no freshers']"),
    )
    score_threshold: Mapped[int] = mapped_column(Integer, server_default=text("70"))
    max_apps_per_day: Mapped[int] = mapped_column(Integer, server_default=text("10"))
    schedule_cron: Mapped[str] = mapped_column(String(100), server_default=text("'0 7 * * *'"))
    telegram_chat_id: Mapped[str | None] = mapped_column(String(100))
    llm_provider: Mapped[str] = mapped_column(String(50), server_default=text("'gemini'"))
    llm_quality_mode: Mapped[str] = mapped_column(String(50), server_default=text("'balanced'"))
    enabled_boards: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("ARRAY['wellfound','internshala']"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    def __repr__(self) -> str:
        return f"UserPreference(id={self.id!r}, user_id={self.user_id!r})"


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("board", "external_id", name="jobs_board_external_id_unique"),
        UniqueConstraint("content_hash", name="jobs_content_hash_unique"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    board: Mapped[str] = mapped_column(String(50), nullable=False)
    external_id: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(String(255))
    work_type: Mapped[str | None] = mapped_column(String(50))
    salary_min_inr: Mapped[int | None] = mapped_column(Integer)
    salary_max_inr: Mapped[int | None] = mapped_column(Integer)
    experience_level: Mapped[str | None] = mapped_column(String(50))
    skills_required: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(50), server_default=text("'new'"))

    def __repr__(self) -> str:
        return f"Job(id={self.id!r}, board={self.board!r}, title={self.title!r}, company={self.company!r})"


class JobScore(Base):
    __tablename__ = "job_scores"
    __table_args__ = (
        CheckConstraint("total_score BETWEEN 0 AND 100", name="job_scores_total_score_check"),
        CheckConstraint("technical_match BETWEEN 0 AND 100", name="job_scores_technical_match_check"),
        CheckConstraint("experience_match BETWEEN 0 AND 100", name="job_scores_experience_match_check"),
        CheckConstraint("domain_match BETWEEN 0 AND 100", name="job_scores_domain_match_check"),
        CheckConstraint("location_match BETWEEN 0 AND 100", name="job_scores_location_match_check"),
        CheckConstraint("growth_potential BETWEEN 0 AND 100", name="job_scores_growth_potential_check"),
        CheckConstraint("recommendation IN ('APPLY','SKIP','STRETCH')", name="job_scores_recommendation_check"),
        UniqueConstraint("job_id", "resume_id", name="job_scores_unique"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    job_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    resume_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False)
    total_score: Mapped[int] = mapped_column(Integer, nullable=False)
    technical_match: Mapped[int | None] = mapped_column(Integer)
    experience_match: Mapped[int | None] = mapped_column(Integer)
    domain_match: Mapped[int | None] = mapped_column(Integer)
    location_match: Mapped[int | None] = mapped_column(Integer)
    growth_potential: Mapped[int | None] = mapped_column(Integer)
    missing_skills: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    matching_skills: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    score_explanation: Mapped[str | None] = mapped_column(Text)
    recommendation: Mapped[str | None] = mapped_column(String(20))
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    def __repr__(self) -> str:
        return f"JobScore(id={self.id!r}, job_id={self.job_id!r}, total_score={self.total_score!r})"


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    job_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("jobs.id"), nullable=False)
    resume_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("resumes.id"), nullable=False)
    trace_id: Mapped[str] = mapped_column(UUID(as_uuid=False), unique=True, nullable=False, server_default=text("gen_random_uuid()"))
    tailored_resume_pdf_path: Mapped[str | None] = mapped_column(Text)
    tailored_resume_docx_path: Mapped[str | None] = mapped_column(Text)
    is_dream_company: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    status: Mapped[str] = mapped_column(String(50), server_default=text("'queued'"))
    failure_reason: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"Application(id={self.id!r}, job_id={self.job_id!r}, status={self.status!r})"


class CoverLetter(Base):
    __tablename__ = "cover_letters"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    application_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("applications.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    word_count: Mapped[int | None] = mapped_column(Integer)
    tone: Mapped[str] = mapped_column(String(50), server_default=text("'professional'"))
    fact_check_passed: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    generation_attempts: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    def __repr__(self) -> str:
        return f"CoverLetter(id={self.id!r}, application_id={self.application_id!r})"


class AgentLog(Base):
    __tablename__ = "agent_logs"
    __table_args__ = (CheckConstraint("confidence BETWEEN 0 AND 1", name="agent_logs_confidence_check"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    application_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    trace_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    field_name: Mapped[str | None] = mapped_column(String(255))
    action_type: Mapped[str | None] = mapped_column(String(100))
    action_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    confidence: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str | None] = mapped_column(String(50))
    screenshot_path: Mapped[str | None] = mapped_column(Text)
    attempt_number: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    def __repr__(self) -> str:
        return f"AgentLog(id={self.id!r}, application_id={self.application_id!r}, step={self.step_number!r})"


class ApplicationEvent(Base):
    __tablename__ = "application_events"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    application_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("applications.id", ondelete="CASCADE"))
    trace_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    event_data: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    def __repr__(self) -> str:
        return f"ApplicationEvent(id={self.id!r}, event_type={self.event_type!r})"


class QAMemory(Base):
    __tablename__ = "qa_memory"
    __table_args__ = (UniqueConstraint("question_hash", name="qa_memory_hash_unique"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    question_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_category: Mapped[str | None] = mapped_column(String(50))
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, server_default=text("1.0"))
    board: Mapped[str | None] = mapped_column(String(50))
    company: Mapped[str | None] = mapped_column(String(255))
    used_count: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    def __repr__(self) -> str:
        return f"QAMemory(id={self.id!r}, question_hash={self.question_hash!r})"


class FormTemplateCache(Base):
    __tablename__ = "form_template_cache"
    __table_args__ = (UniqueConstraint("board", "page_url_pattern", name="form_template_cache_unique"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    board: Mapped[str] = mapped_column(String(50), nullable=False)
    page_url_pattern: Mapped[str] = mapped_column(String(500), nullable=False)
    page_structure_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    field_map: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    cached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    hit_count: Mapped[int] = mapped_column(Integer, server_default=text("1"))

    def __repr__(self) -> str:
        return f"FormTemplateCache(id={self.id!r}, board={self.board!r})"


class CompanyCache(Base):
    __tablename__ = "company_cache"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    company_name_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    known: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    industry: Mapped[str | None] = mapped_column(Text)
    what_they_do: Mapped[str | None] = mapped_column(Text)
    mission: Mapped[str | None] = mapped_column(Text)
    values_text: Mapped[str | None] = mapped_column(Text)
    recent_news: Mapped[str | None] = mapped_column(Text)
    culture_signals: Mapped[str | None] = mapped_column(Text)
    why_interesting: Mapped[str | None] = mapped_column(Text)
    cached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("(NOW() + INTERVAL '7 days')"))

    def __repr__(self) -> str:
        return f"CompanyCache(id={self.id!r}, company_name_key={self.company_name_key!r})"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), server_default=text("'pending'"))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    jobs_found: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    apps_attempted: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    apps_completed: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    result_summary: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)

    def __repr__(self) -> str:
        return f"Task(id={self.id!r}, task_type={self.task_type!r}, status={self.status!r})"


DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://autohire:yourpassword@db:5432/autohire")
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Index("idx_application_events_trace_id", ApplicationEvent.trace_id)
Index("idx_application_events_created_at", ApplicationEvent.created_at.desc())
Index("idx_jobs_status", Job.status)
Index("idx_jobs_board", Job.board)
Index("idx_jobs_scraped_at", Job.scraped_at.desc())
Index("idx_job_scores_total_score", JobScore.total_score.desc())
Index("idx_applications_status", Application.status)
Index("idx_applications_queued_at", Application.queued_at.desc())
Index("idx_agent_logs_application_id", AgentLog.application_id)
Index("idx_agent_logs_trace_id", AgentLog.trace_id)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
