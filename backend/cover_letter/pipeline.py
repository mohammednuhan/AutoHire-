from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from cover_letter.company_researcher import research_company
from cover_letter.generator import CoverLetterGenerationError, generate_cover_letter
from cover_letter.models import CompanyResearch, CoverLetterResult, ValidationResult
from cover_letter.validator import validate_cover_letter
from database.models import Application, ApplicationEvent, CoverLetter, Job
from database.session import AsyncSessionLocal
from llm.client import LLMRouter
from notifications.telegram import send_needs_human_alert
from schemas.api_schemas import ResumeProfile
from websocket import websocket_manager

logger = logging.getLogger("autohire.cover_letter.pipeline")

MAX_GENERATION_ATTEMPTS = 3


async def generate_and_validate(
    job: Job,
    profile: ResumeProfile,
    application_id: str,
    llm_router: LLMRouter,
    company_research: CompanyResearch | None = None,
) -> CoverLetterResult:
    company_research = company_research or await research_company(job.company, llm_router)
    previous_failure_reason: str | None = None
    unsupported_claims: list[str] = []
    last_validation: ValidationResult | None = None

    for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
        try:
            cover_letter_text = await generate_cover_letter(
                job,
                profile,
                company_research,
                llm_router,
                previous_failure_reason=previous_failure_reason,
                unsupported_claims=unsupported_claims,
            )
        except CoverLetterGenerationError as exc:
            logger.warning(
                "cover_letter_generation_failed",
                extra={"application_id": application_id, "attempt": attempt, "error": str(exc)},
            )
            last_validation = ValidationResult(
                passed=False,
                unsupported_claims=[str(exc)],
                word_count=0,
                failure_reason="HALLUCINATED_CLAIMS",
            )
            previous_failure_reason = last_validation.failure_reason
            unsupported_claims = last_validation.unsupported_claims
            continue

        validation = await validate_cover_letter(cover_letter_text, profile, job, llm_router)
        last_validation = validation

        if validation.passed:
            await save_cover_letter(application_id, cover_letter_text, validation, attempt)
            return CoverLetterResult(
                success=True,
                content=cover_letter_text,
                validation=validation,
                attempts=attempt,
            )

        previous_failure_reason = validation.failure_reason
        unsupported_claims = validation.unsupported_claims

    await update_application_status(
        application_id,
        "needs_human",
        failure_reason="COVER_LETTER_VALIDATION_FAILED",
    )
    await notify_human(application_id, reason="Cover letter could not be verified after 3 attempts")
    return CoverLetterResult(success=False, validation=last_validation, attempts=MAX_GENERATION_ATTEMPTS)


async def save_cover_letter(
    application_id: str,
    cover_letter_text: str,
    validation: ValidationResult,
    generation_attempts: int,
) -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.scalar(select(CoverLetter).where(CoverLetter.application_id == application_id))
        if existing is None:
            existing = CoverLetter(application_id=application_id, content=cover_letter_text)
            db.add(existing)
        existing.content = cover_letter_text
        existing.word_count = validation.word_count
        existing.fact_check_passed = validation.passed
        existing.generation_attempts = generation_attempts
        await db.commit()


async def update_application_status(
    application_id: str,
    status: str,
    failure_reason: str | None = None,
) -> None:
    async with AsyncSessionLocal() as db:
        application = await db.get(Application, application_id)
        if application is None:
            raise ValueError(f"Application not found: {application_id}")
        application.status = status
        application.failure_reason = failure_reason
        if status == "agent_processing" and application.started_at is None:
            application.started_at = datetime.now(timezone.utc)
        await db.commit()


async def notify_human(application_id: str, reason: str) -> None:
    company = "Unknown"
    role = "Unknown"
    async with AsyncSessionLocal() as db:
        row = await db.execute(
            select(Application, Job)
            .join(Job, Application.job_id == Job.id)
            .where(Application.id == application_id)
        )
        result = row.first()
        if result is not None:
            _application, job = result
            company = job.company
            role = job.title
    event = {
        "event": "NEEDS_HUMAN",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "application_id": application_id,
        "reason": "PREREQ_FAILED",
        "message": reason,
    }
    await _publish_event(event, application_id=application_id)
    await send_needs_human_alert(
        application_id=application_id,
        company=company,
        role=role,
        field_name="Cover letter",
        reason="PREREQ_FAILED",
        screenshot_available=False,
    )


async def _publish_event(
    event: dict[str, Any],
    application_id: str | None = None,
    trace_id: str | None = None,
) -> None:
    async with AsyncSessionLocal() as db:
        db.add(
            ApplicationEvent(
                application_id=application_id,
                trace_id=trace_id,
                event_type=str(event["event"]),
                event_data=event,
            )
        )
        await db.commit()
    await websocket_manager.publish(event)
