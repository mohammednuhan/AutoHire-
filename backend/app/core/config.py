from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"
    user_timezone: str = "Asia/Kolkata"
    log_level: str = "INFO"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    database_url: str = "postgresql+asyncpg://autohire:change-me@postgres:5432/autohire"
    redis_url: str = "redis://redis:6379/0"

    stop_requested_key: str = "STOP_REQUESTED"
    scheduler_lock_key: str = "AUTOHIRE_SCHEDULER_LOCK"
    scheduler_lock_ttl_seconds: int = 7200
    scheduler_lock_heartbeat_seconds: int = 900

    llm_dev_provider: str = "gemini"
    llm_dev_model: str = "gemini-2.0-flash"
    llm_prod_provider: str = "anthropic"
    llm_prod_model: str = "claude-sonnet-4-6"
    gemini_api_key: str | None = None
    anthropic_api_key: str | None = None
    enable_extended_thinking_for_cover_letters: bool = True
    enable_extended_thinking_for_complex_screening: bool = True

    score_auto_queue_threshold: int = 70
    confidence_gate: float = 0.80
    daily_application_cap: int = 10
    daily_application_cap_max: int = 30
    linkedin_phase: int = 3
    linkedin_daily_cap: int = 5

    browser_use_version: str = "0.12.2"
    screenshot_max_width: int = 1280
    screenshot_max_height: int = 720

    cover_letter_min_words: int = 200
    cover_letter_max_words: int = 300
    cover_letter_paragraphs: int = 3
    resume_format: str = "single_column_text"

    backup_retention_weeks: int = 4
    backup_cron: str = Field(default="0 3 * * 0")

    @field_validator("score_auto_queue_threshold")
    @classmethod
    def validate_score_threshold(cls, value: int) -> int:
        if not 0 <= value <= 100:
            raise ValueError("SCORE_AUTO_QUEUE_THRESHOLD must be between 0 and 100")
        return value

    @field_validator("confidence_gate")
    @classmethod
    def validate_confidence_gate(cls, value: float) -> float:
        if not 0 <= value <= 1:
            raise ValueError("CONFIDENCE_GATE must be between 0 and 1")
        return value

    @field_validator("daily_application_cap")
    @classmethod
    def validate_daily_cap(cls, value: int) -> int:
        if not 0 <= value <= 30:
            raise ValueError("DAILY_APPLICATION_CAP must be between 0 and 30")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
