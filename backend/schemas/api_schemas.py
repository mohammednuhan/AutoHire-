from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class EducationItem(BaseModel):
    institution: str
    degree: str
    field: str | None = None
    graduation_year: int | None = None
    gpa: str | None = None
    relevant_courses: list[str] = Field(default_factory=list)


class ExperienceItem(BaseModel):
    company: str
    role: str
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool = False
    location: str | None = None
    description: list[str] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)


class ProjectItem(BaseModel):
    name: str
    description: str | None = None
    tech_stack: list[str] = Field(default_factory=list)
    url: str | None = None
    duration: str | None = None


class SkillsProfile(BaseModel):
    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    databases: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    cloud: list[str] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)


class CertificationItem(BaseModel):
    name: str
    issuer: str | None = None
    year: int | None = None


class ResumeProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    full_name: str
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
    summary: str | None = None
    education: list[EducationItem] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    skills: SkillsProfile = Field(default_factory=SkillsProfile)
    certifications: list[CertificationItem] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    languages_spoken: list[str] = Field(default_factory=list)


class UserPreferences(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    target_roles: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    work_type: Literal["remote", "hybrid", "onsite", "any"] = "any"
    salary_min_inr: int | None = None
    salary_max_inr: int | None = None
    experience_level: Literal["internship", "entry", "mid", "senior"] = "entry"
    job_types: list[str] = Field(default_factory=lambda: ["fulltime"])
    industry_include: list[str] = Field(default_factory=list)
    industry_exclude: list[str] = Field(default_factory=list)
    blacklisted_companies: list[str] = Field(default_factory=list)
    dream_companies: list[str] = Field(default_factory=list)
    keyword_blacklist: list[str] = Field(
        default_factory=lambda: ["10+ years", "US citizenship required", "no freshers"]
    )
    score_threshold: int = Field(default=70, ge=50, le=95)
    max_apps_per_day: int = Field(default=10, ge=1, le=30)
    schedule_cron: str = "0 7 * * *"
    telegram_chat_id: str | None = None
    llm_provider: Literal["gemini", "claude", "ollama"] = "gemini"
    llm_quality_mode: Literal["fast", "balanced", "maximum"] = "balanced"
    enabled_boards: list[str] = Field(default_factory=lambda: ["wellfound", "internshala"])


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    board: str
    external_id: str
    title: str
    company: str
    url: str
    location: str | None = None
    work_type: str | None = None
    salary_min_inr: int | None = None
    salary_max_inr: int | None = None
    experience_level: str | None = None
    skills_required: list[str] = Field(default_factory=list)
    posted_at: datetime | None = None
    scraped_at: datetime
    status: str
    total_score: int | None = None
    recommendation: Literal["APPLY", "SKIP", "STRETCH"] | None = None


class JobsPageResponse(BaseModel):
    page: int
    per_page: int
    total: int
    items: list[JobResponse]


class ScoreBreakdown(BaseModel):
    total_score: int = Field(ge=0, le=100)
    technical_match: int | None = Field(default=None, ge=0, le=100)
    experience_match: int | None = Field(default=None, ge=0, le=100)
    domain_match: int | None = Field(default=None, ge=0, le=100)
    location_match: int | None = Field(default=None, ge=0, le=100)
    growth_potential: int | None = Field(default=None, ge=0, le=100)
    missing_skills: list[str] = Field(default_factory=list)
    matching_skills: list[str] = Field(default_factory=list)
    score_explanation: str | None = None
    recommendation: Literal["APPLY", "SKIP", "STRETCH"] | None = None
    scored_at: datetime | None = None


class JobDetailResponse(JobResponse):
    description: str | None = None
    content_hash: str | None = None
    score_breakdown: ScoreBreakdown | None = None


class CoverLetterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    application_id: UUID
    content: str
    word_count: int | None = None
    tone: str = "professional"
    fact_check_passed: bool = False
    generation_attempts: int = 1
    created_at: datetime


class AgentLogEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    application_id: UUID
    trace_id: UUID
    step_number: int
    field_name: str | None = None
    action_type: str | None = None
    action_data: dict[str, Any] | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    status: str | None = None
    screenshot_path: str | None = None
    attempt_number: int = 1
    error_message: str | None = None
    created_at: datetime


class ApplicationEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    application_id: UUID | None = None
    trace_id: UUID | None = None
    event_type: str
    event_data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ApplicationListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    resume_id: UUID
    trace_id: UUID
    title: str | None = None
    company: str | None = None
    board: str | None = None
    is_dream_company: bool = False
    status: str
    failure_reason: str | None = None
    queued_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    submitted_at: datetime | None = None


class ApplicationDetailResponse(ApplicationListItem):
    notes: str | None = None
    tailored_resume_pdf_path: str | None = None
    tailored_resume_docx_path: str | None = None
    job: JobDetailResponse | None = None
    cover_letter: CoverLetterResponse | None = None
    agent_log: list[AgentLogEntry] = Field(default_factory=list)
    events: list[ApplicationEventResponse] = Field(default_factory=list)


class NeedsHumanPayload(BaseModel):
    application_id: UUID
    trace_id: UUID
    reason: str
    message: str
    field_name: str | None = None
    screenshot_path: str | None = None
    options: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)


class AgentStatusResponse(BaseModel):
    is_running: bool
    stop_requested: bool
    active_application_id: UUID | None = None
    active_trace_id: UUID | None = None
    current_step: str | None = None
    last_heartbeat_at: datetime | None = None
    lock_expires_at: datetime | None = None


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_type: str
    status: str
    scheduled_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    jobs_found: int = 0
    apps_attempted: int = 0
    apps_completed: int = 0
    result_summary: str | None = None
    error_message: str | None = None


class AgentRunRequest(BaseModel):
    boards: list[str] | None = None


class AgentRunResponse(BaseModel):
    task_id: UUID
    status: Literal["started"]


class MetricsResponse(BaseModel):
    jobs_discovered: int = 0
    jobs_scored: int = 0
    applications_queued: int = 0
    applications_submitted: int = 0
    applications_needing_human: int = 0
    applications_failed: int = 0
    average_score: float | None = None
    daily_cap: int
    apps_used_today: int
    updated_at: datetime


class ErrorResponse(BaseModel):
    error: str
    message: str


class WebSocketEvent(BaseModel):
    event: str
    timestamp: datetime


class AgentStatusEvent(WebSocketEvent):
    event: Literal["AGENT_STATUS"] = "AGENT_STATUS"
    status: Literal["idle", "running", "paused", "error"]


class RunStartedEvent(WebSocketEvent):
    event: Literal["RUN_STARTED"] = "RUN_STARTED"
    task_id: UUID
    boards: list[str]


class RunCompletedEvent(WebSocketEvent):
    event: Literal["RUN_COMPLETED"] = "RUN_COMPLETED"
    task_id: UUID
    jobs_found: int
    apps_attempted: int
    apps_completed: int
    duration_seconds: int


class JobDiscoveredEvent(WebSocketEvent):
    event: Literal["JOB_DISCOVERED"] = "JOB_DISCOVERED"
    job_id: UUID
    company: str
    title: str
    board: str
    score: int = Field(ge=0, le=100)
    recommendation: Literal["APPLY", "SKIP", "STRETCH"]


class ApplicationStartedEvent(WebSocketEvent):
    event: Literal["APPLICATION_STARTED"] = "APPLICATION_STARTED"
    application_id: UUID
    trace_id: UUID
    company: str
    role: str


class BrowserActionEvent(WebSocketEvent):
    event: Literal["BROWSER_ACTION"] = "BROWSER_ACTION"
    trace_id: UUID
    step: int
    action: str
    field: str
    confidence: float = Field(ge=0, le=1)


class LLMCallEvent(WebSocketEvent):
    event: Literal["LLM_CALL"] = "LLM_CALL"
    trace_id: UUID
    purpose: str
    model: str
    tokens: int


class ValidationResultEvent(WebSocketEvent):
    event: Literal["VALIDATION_RESULT"] = "VALIDATION_RESULT"
    trace_id: UUID
    field: str
    confidence: float = Field(ge=0, le=1)
    passed: bool


class ApplicationSuccessEvent(WebSocketEvent):
    event: Literal["APPLICATION_SUCCESS"] = "APPLICATION_SUCCESS"
    application_id: UUID
    trace_id: UUID
    company: str
    role: str
    status: Literal["ready_to_submit"]


class ApplicationFailedEvent(WebSocketEvent):
    event: Literal["APPLICATION_FAILED"] = "APPLICATION_FAILED"
    application_id: UUID
    trace_id: UUID
    reason: str
    step: int


class NeedsHumanEvent(WebSocketEvent):
    event: Literal["NEEDS_HUMAN"] = "NEEDS_HUMAN"
    application_id: UUID
    trace_id: UUID
    company: str
    role: str
    reason: Literal[
        "LOW_CONFIDENCE",
        "DREAM_COMPANY",
        "SALARY_QUESTION",
        "SCREENING_QUESTION",
        "PREREQ_FAILED",
    ]
    field_name: str
    question_text: str
    draft_answer: str | None
    confidence: float = Field(ge=0, le=1)
    screenshot_url: str
    expires_at: datetime


class HealthCheckEvent(WebSocketEvent):
    event: Literal["HEALTH_CHECK"] = "HEALTH_CHECK"
    db: Literal["ok"]
    redis: Literal["ok"]
    agent: Literal["idle", "running", "paused"]


class MorningSummaryEvent(WebSocketEvent):
    event: Literal["MORNING_SUMMARY"] = "MORNING_SUMMARY"
    date: str
    jobs_scanned: int
    new_high_score_jobs: int
    apps_attempted: int
    apps_completed: int
    apps_needs_review: int


class ErrorEvent(WebSocketEvent):
    event: Literal["ERROR"] = "ERROR"
    error_code: Literal[
        "LLM_FAILURE",
        "RUNGUARD_FAIL_INTERNET",
        "RUNGUARD_FAIL_DB",
        "DISK_FULL",
        "REDIS_UNAVAILABLE",
        "SCAN_FAILED",
    ]
    message: str


TypedWebSocketEvent = (
    AgentStatusEvent
    | RunStartedEvent
    | RunCompletedEvent
    | JobDiscoveredEvent
    | ApplicationStartedEvent
    | BrowserActionEvent
    | LLMCallEvent
    | ValidationResultEvent
    | ApplicationSuccessEvent
    | ApplicationFailedEvent
    | NeedsHumanEvent
    | HealthCheckEvent
    | MorningSummaryEvent
    | ErrorEvent
)
