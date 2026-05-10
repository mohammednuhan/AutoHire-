from __future__ import annotations

import json
import logging
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from browser.models import Action
from cover_letter.text_utils import json_payload
from database.models import Job
from llm.client import LLMFailure, LLMRouter
from llm.prompts import APPLICATION_PLAN_PROMPT, APPLICATION_PLAN_SYSTEM
from resume.formatting import format_education, format_experience
from resume.safety import ContentSafetyError, sanitize_user_content
from schemas.api_schemas import ResumeProfile

logger = logging.getLogger("autohire.browser.planner")


class PlanningError(Exception):
    pass


async def plan_application(
    job_url: str,
    job: Job,
    profile: ResumeProfile,
    cover_letter: str,
    resume_pdf_path: str,
    llm_router: LLMRouter,
) -> list[Action]:
    try:
        safe_job_url = sanitize_user_content(job_url)[:1000]
        safe_title = sanitize_user_content(job.title)[:500]
        safe_company = sanitize_user_content(job.company)[:255]
        safe_cover_letter = sanitize_user_content(cover_letter)[:4000]
    except ContentSafetyError as exc:
        raise PlanningError(f"Unsafe planning input rejected: {exc}") from exc

    prompt = APPLICATION_PLAN_PROMPT.format(
        job_url=safe_job_url,
        job_title=safe_title,
        job_company=safe_company,
        full_name=profile.full_name,
        email=profile.email or "",
        phone=profile.phone or "",
        location=profile.location or "",
        linkedin_url=profile.linkedin_url or "",
        github_url=profile.github_url or "",
        portfolio_url=profile.portfolio_url or "",
        education=format_education(profile.education),
        experience=format_experience(profile.experience),
        cover_letter=safe_cover_letter,
        resume_pdf_path=resume_pdf_path,
        first_name=_first_name(profile.full_name),
    )
    try:
        response = await llm_router.call_with_retry(
            task_type="reason",
            prompt=prompt,
            system=APPLICATION_PLAN_SYSTEM,
            response_format="json",
            max_retries=3,
            trace_id=str(uuid4()),
        )
        return _parse_actions(response)
    except (LLMFailure, ValueError, ValidationError) as exc:
        logger.warning("application_planning_failed", extra={"job_id": job.id, "error": str(exc)})
        return _fallback_plan(safe_job_url, profile, safe_cover_letter, resume_pdf_path)


def _parse_actions(response: str) -> list[Action]:
    payload: Any
    try:
        payload = json_payload(response)
        if isinstance(payload, dict):
            payload = payload.get("actions")
    except json.JSONDecodeError:
        payload = json.loads(response.strip())

    if not isinstance(payload, list):
        raise ValueError("Planner response must be a JSON array")

    actions = [Action.model_validate(item) for item in payload]
    if not actions:
        raise ValueError("Planner returned an empty action list")
    return _normalize_steps(actions)


def _normalize_steps(actions: list[Action]) -> list[Action]:
    ordered = sorted(actions, key=lambda action: action.step)
    normalized: list[Action] = []
    for index, action in enumerate(ordered, start=1):
        data = action.model_dump()
        data["step"] = index
        normalized.append(Action.model_validate(data))
    return normalized


def _fallback_plan(
    job_url: str,
    profile: ResumeProfile,
    cover_letter: str,
    resume_pdf_path: str,
) -> list[Action]:
    actions: list[Action] = [
        Action(
            step=1,
            action="navigate",
            url=job_url,
            expected_state="Application form page loaded",
        )
    ]
    fields = [
        ("First name input", _first_name(profile.full_name), "First name field shows the name"),
        ("Last name input", _last_name(profile.full_name), "Last name field shows the name"),
        ("Email address", profile.email, "Email field populated"),
        ("Phone number", profile.phone, "Phone field populated"),
        ("Current location", profile.location, "Location field populated"),
        ("LinkedIn profile", profile.linkedin_url, "LinkedIn field populated"),
        ("GitHub profile", profile.github_url, "GitHub field populated"),
        ("Portfolio website", profile.portfolio_url, "Portfolio field populated"),
        ("Work authorization", "Eligible to work in India", "Work authorization field populated"),
        ("Visa sponsorship", "No sponsorship required", "Visa sponsorship field populated"),
        ("Cover letter text area", cover_letter, "Cover letter field populated"),
    ]
    step = 2
    for field_description, value, expected_state in fields:
        if not value:
            continue
        actions.append(
            Action(
                step=step,
                action="fill",
                field_description=field_description,
                value=value,
                expected_state=expected_state,
            )
        )
        step += 1
    actions.append(
        Action(
            step=step,
            action="upload",
            field_description="Resume upload button",
            file_path=resume_pdf_path,
            expected_state="Resume filename visible in upload area",
        )
    )
    actions.append(
        Action(
            step=step + 1,
            action="screenshot",
            field_description="Final form review",
            expected_state="All fields filled, submit button visible",
        )
    )
    return actions


def _first_name(full_name: str) -> str:
    return full_name.split()[0] if full_name.split() else full_name


def _last_name(full_name: str) -> str:
    parts = full_name.split()
    return " ".join(parts[1:]) if len(parts) > 1 else ""
