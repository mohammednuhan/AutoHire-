from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from agent.runguard import run_preflight_checks
from browser.browser_use_driver import BrowserUseDriver
from browser.models import ActionValidationResult, ApplicationResult
from browser.planner import plan_application
from browser.state_machine import (
    ApplicationStateMachine,
    publish_ws_event,
    update_application_status,
)
from browser.template_cache import apply_cached_selectors, get_cached_field_map, save_field_map
from browser.validator import validate_action
from database.models import Application, CoverLetter, Job, Resume
from database.session import AsyncSessionLocal
from llm.client import LLMRouter
from memory.qa_memory import save_answer
from schemas.api_schemas import ResumeProfile

logger = logging.getLogger("autohire.agent.applicant")


async def run_application(
    application_id: str,
    llm_router: LLMRouter,
    approved_answers: dict[str, str] | None = None,
) -> ApplicationResult:
    """Top-level function called by the orchestrator for each prepared application."""
    application, job, profile, cover_letter = await load_application_bundle(application_id)
    trace_id = str(application.trace_id)
    state_machine = ApplicationStateMachine()

    if application.is_dream_company:
        await state_machine.set_needs_human(
            application_id=application_id,
            trace_id=trace_id,
            reason="DREAM_COMPANY",
            question_text=(
                "This is a dream company application. Review carefully before proceeding."
            ),
        )
        return ApplicationResult(status="needs_human")

    guard = await run_preflight_checks()
    if not guard.passed:
        await update_application_status(
            application_id,
            "interrupted",
            failure_reason="RUNGUARD_FAILED",
        )
        return ApplicationResult(status="interrupted", failure_reason="RUNGUARD_FAILED")

    await update_application_status(application_id, "agent_processing")
    await publish_ws_event(
        "APPLICATION_STARTED",
        application_id=application_id,
        trace_id=trace_id,
        company=job.company,
        role=job.title,
    )

    driver = BrowserUseDriver()
    try:
        resume_path = (
            application.tailored_resume_docx_path
            if job.board == "naukri" and application.tailored_resume_docx_path
            else application.tailored_resume_pdf_path
        ) or ""
        action_plan = await plan_application(
            job_url=job.url,
            job=job,
            profile=profile,
            cover_letter=cover_letter.content,
            resume_pdf_path=resume_path,
            llm_router=llm_router,
        )
        cached_field_map = await get_cached_field_map(job.board, job.url)
        action_plan = apply_cached_selectors(action_plan, cached_field_map)
        action_plan = _apply_approved_answers(action_plan, approved_answers or {})

        await driver.start(headless=True)
        result = await state_machine.run(
            application_id=application_id,
            action_plan=action_plan,
            driver=driver,
            llm_router=llm_router,
            trace_id=trace_id,
        )
        if result.status in {"ready_to_submit", "submitted"}:
            await save_field_map(job.board, job.url, action_plan)
        return result
    except Exception as exc:
        logger.exception("application_agent_failed", extra={"application_id": application_id})
        await update_application_status(
            application_id,
            "interrupted",
            failure_reason=f"UNHANDLED_ERROR: {type(exc).__name__}",
        )
        await publish_ws_event(
            "APPLICATION_FAILED",
            application_id=application_id,
            trace_id=trace_id,
            reason="UNHANDLED_ERROR",
            step=None,
        )
        raise
    finally:
        await driver.close()


async def submit_application(application_id: str, llm_router: LLMRouter) -> ApplicationResult:
    application, job, _profile, _cover_letter = await load_application_bundle(application_id)
    trace_id = str(application.trace_id)
    guard = await run_preflight_checks()
    if not guard.passed:
        await update_application_status(
            application_id,
            "interrupted",
            failure_reason="RUNGUARD_FAILED",
        )
        return ApplicationResult(status="interrupted", failure_reason="RUNGUARD_FAILED")

    driver = BrowserUseDriver()
    state_machine = ApplicationStateMachine()
    try:
        await driver.start(headless=True)
        await driver.navigate(job.url)
        validation: ActionValidationResult | None = None
        for attempt in range(1, 3):
            result = await driver.click_element("Submit application button")
            screenshot_path = await state_machine.save_screenshot(
                application_id,
                999,
                result.screenshot_bytes,
                suffix=f"submit_attempt_{attempt}",
            )
            validation = await validate_action(
                screenshot_bytes=result.screenshot_bytes,
                expected_state=(
                    "Application confirmation page visible with application received, "
                    "thank you, or reference number"
                ),
                action_description="Click final submit button",
                llm_router=llm_router,
            )
            await state_machine.log_step(
                application_id=application_id,
                trace_id=trace_id,
                step_number=999,
                field_name="Final submit",
                action_type="click",
                status="complete" if validation.passed else "failed_validation",
                confidence=validation.confidence,
                screenshot_path=screenshot_path,
                attempt_number=attempt,
                error_message=validation.error_text or validation.failure_reason,
            )
            if validation.passed:
                await update_application_status(application_id, "submitted")
                await publish_ws_event(
                    "APPLICATION_SUCCESS",
                    application_id=application_id,
                    trace_id=trace_id,
                    status="submitted",
                    company=job.company,
                    role=job.title,
                )
                return ApplicationResult(status="submitted")

        await state_machine.set_needs_human(
            application_id=application_id,
            trace_id=trace_id,
            reason="SUBMIT_CONFIRMATION_FAILED",
            field_name="Final submit",
            confidence=validation.confidence if validation else None,
            question_text="Submit confirmation could not be verified.",
            step=999,
            driver=driver,
        )
        return ApplicationResult(status="needs_human", paused_at_step=999)
    finally:
        await driver.close()


async def resume_application_after_human(
    trace_id: str,
    field_name: str,
    answer: str,
    llm_router: LLMRouter,
) -> ApplicationResult:
    application = await load_application_by_trace_id(trace_id)
    await save_human_answer(application.id, trace_id, field_name, answer)
    return await run_application(
        str(application.id),
        llm_router,
        approved_answers={field_name: answer},
    )


async def load_application_bundle(
    application_id: str,
) -> tuple[Application, Job, ResumeProfile, CoverLetter]:
    async with AsyncSessionLocal() as db:
        row = await db.execute(
            select(Application, Job, Resume, CoverLetter)
            .join(Job, Application.job_id == Job.id)
            .join(Resume, Application.resume_id == Resume.id)
            .join(CoverLetter, CoverLetter.application_id == Application.id)
            .where(Application.id == application_id)
        )
        result = row.first()
        if result is None:
            raise ValueError(f"Prepared application not found: {application_id}")
        application, job, resume, cover_letter = result
        if not application.tailored_resume_pdf_path:
            raise ValueError(f"Application has no tailored resume PDF: {application_id}")
        return application, job, ResumeProfile.model_validate(resume.profile_json), cover_letter


async def load_application_by_trace_id(trace_id: str) -> Application:
    async with AsyncSessionLocal() as db:
        application = await db.scalar(select(Application).where(Application.trace_id == trace_id))
        if application is None:
            raise ValueError(f"Application not found for trace_id: {trace_id}")
        return application


async def save_human_answer(
    application_id: str,
    trace_id: str,
    field_name: str,
    answer: str,
) -> None:
    await save_answer(
        question=field_name,
        answer=answer,
        category="human_input",
        board="manual",
        company="",
    )
    await publish_ws_event(
        "VALIDATION_RESULT",
        application_id=application_id,
        trace_id=trace_id,
        field=field_name,
        confidence=1.0,
        passed=True,
    )


def _apply_approved_answers(actions: list[Any], approved_answers: dict[str, str]) -> list[Any]:
    if not approved_answers:
        return actions
    normalized_answers = {key.strip().lower(): value for key, value in approved_answers.items()}
    patched = []
    for action in actions:
        key = (action.field_description or "").strip().lower()
        if key in normalized_answers and (
            str(action.value or "").strip().upper() == "NEEDS_HUMAN"
            or str(action.option_value or "").strip().upper() == "NEEDS_HUMAN"
        ):
            data = action.model_dump()
            data["value"] = normalized_answers[key]
            if data.get("option_value") == "NEEDS_HUMAN":
                data["option_value"] = normalized_answers[key]
            action = action.__class__.model_validate(data)
        patched.append(action)
    return patched
