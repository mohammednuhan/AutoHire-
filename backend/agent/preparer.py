from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from cover_letter.company_researcher import research_company
from cover_letter.pipeline import generate_and_validate
from database.models import Application, ApplicationEvent, Job, Resume
from database.session import AsyncSessionLocal
from llm.client import LLMRouter
from resume.tailor import tailor_resume
from schemas.api_schemas import ResumeProfile
from websocket import websocket_manager

logger = logging.getLogger("autohire.agent.preparer")


async def prepare_application(application_id: str, llm_router: LLMRouter) -> None:
    """
    Called after a job is queued. Runs cover letter + resume tailoring.
    Changes application status: queued -> agent_processing during -> ready_to_submit on success.
    """
    await update_application_status(application_id, "agent_processing")

    try:
        job, profile = await _load_job_and_profile(application_id)
        company_research = await research_company(job.company, llm_router)

        cover_result = await generate_and_validate(
            job,
            profile,
            application_id,
            llm_router,
            company_research=company_research,
        )
        if not cover_result.success:
            return

        tailor_result = await tailor_resume(profile, job, application_id, llm_router)
        if not tailor_result.success:
            await update_application_status(
                application_id,
                "needs_human",
                failure_reason="TAILORING_FAILED",
            )
            return

        await update_application_status(application_id, "ready_to_submit")
        await _publish_success(application_id)
    except Exception as exc:
        logger.exception("application_preparation_failed", extra={"application_id": application_id})
        await update_application_status(
            application_id,
            "needs_human",
            failure_reason="PREPARATION_FAILED",
        )
        await _publish_event(
            {
                "event": "APPLICATION_FAILED",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "application_id": application_id,
                "reason": str(exc),
                "step": 0,
            },
            application_id=application_id,
        )


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


async def _load_job_and_profile(application_id: str) -> tuple[Job, ResumeProfile]:
    async with AsyncSessionLocal() as db:
        row = await db.execute(
            select(Application, Job, Resume)
            .join(Job, Application.job_id == Job.id)
            .join(Resume, Application.resume_id == Resume.id)
            .where(Application.id == application_id)
        )
        result = row.first()
        if result is None:
            raise ValueError(f"Application not found: {application_id}")
        _application, job, resume = result
        return job, ResumeProfile.model_validate(resume.profile_json)


async def _publish_success(application_id: str) -> None:
    async with AsyncSessionLocal() as db:
        row = await db.execute(
            select(Application, Job)
            .join(Job, Application.job_id == Job.id)
            .where(Application.id == application_id)
        )
        result = row.first()
        if result is None:
            return
        application, job = result
        event = {
            "event": "APPLICATION_SUCCESS",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "application_id": application_id,
            "trace_id": application.trace_id,
            "company": job.company,
            "role": job.title,
            "status": "ready_to_submit",
        }
    await _publish_event(event, application_id=application_id, trace_id=event["trace_id"])


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
