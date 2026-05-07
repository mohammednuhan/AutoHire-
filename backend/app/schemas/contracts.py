from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.db.enums import ApplicationStatus, DecisionReason, JobSource


class UserProfileContract(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    full_name: str
    email: str
    phone: str | None = None
    location: str | None = None
    education: dict = Field(default_factory=dict)
    skills: list[str] = Field(default_factory=list)
    links: dict[str, str] = Field(default_factory=dict)
    preferences: dict = Field(default_factory=dict)


class JobPostingContract(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source: JobSource
    title: str
    company_name: str | None = None
    location: str | None = None
    url: HttpUrl
    description: str | None = None
    required_skills: list[str] = Field(default_factory=list)


class ApplicationContract(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_posting_id: str
    status: ApplicationStatus
    score: int | None = Field(default=None, ge=0, le=100)
    confidence: float | None = Field(default=None, ge=0, le=1)
    decision_reason: DecisionReason | None = None


class HumanReviewContract(BaseModel):
    application_id: str
    reason: DecisionReason
    message: str


class AgentLimitsContract(BaseModel):
    score_auto_queue_threshold: int = Field(default=70, ge=0, le=100)
    confidence_gate: float = Field(default=0.80, ge=0, le=1)
    daily_application_cap: int = Field(default=10, ge=0, le=30)
    linkedin_daily_cap: int = Field(default=5, ge=0, le=5)
