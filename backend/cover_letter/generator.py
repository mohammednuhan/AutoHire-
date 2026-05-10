from __future__ import annotations

from uuid import uuid4

from cover_letter.models import CompanyResearch
from database.models import Job
from llm.client import LLMFailure, LLMRouter
from llm.prompts import COVER_LETTER_PROMPT, COVER_LETTER_SYSTEM
from resume.formatting import format_education, format_experience, format_projects, format_skills
from resume.safety import ContentSafetyError, sanitize_user_content
from schemas.api_schemas import ResumeProfile


class CoverLetterGenerationError(Exception):
    pass


async def generate_cover_letter(
    job: Job,
    profile: ResumeProfile,
    company_research: CompanyResearch,
    llm_router: LLMRouter,
    previous_failure_reason: str | None = None,
    unsupported_claims: list[str] | None = None,
) -> str:
    try:
        safe_description = sanitize_user_content(job.description or "")[:3000]
        safe_title = sanitize_user_content(job.title)[:500]
        safe_company = sanitize_user_content(job.company)[:255]
    except ContentSafetyError as exc:
        raise CoverLetterGenerationError(f"Unsafe job content rejected: {exc}") from exc

    correction_instructions = ""
    if previous_failure_reason:
        correction_instructions = (
            "Previous attempt failed because: "
            f"{previous_failure_reason}.\n"
            "Unsupported claims or rule violations to avoid: "
            f"{unsupported_claims or []}\n"
            "Regenerate from the profile only and satisfy every strict rule.\n"
        )

    prompt = COVER_LETTER_PROMPT.format(
        full_name=profile.full_name,
        skills=format_skills(profile.skills),
        experience=format_experience(profile.experience),
        projects=format_projects(profile.projects),
        education=format_education(profile.education),
        job_title=safe_title,
        job_company=safe_company,
        job_description=safe_description,
        job_skills_required=job.skills_required or [],
        company_what_they_do=company_research.what_they_do or "Not available",
        company_culture_signals=company_research.culture_signals or "Not available",
        company_why_interesting=company_research.why_interesting or "Not available",
        correction_instructions=correction_instructions,
    )
    try:
        response = await llm_router.call_with_retry(
            task_type="write",
            prompt=prompt,
            system=COVER_LETTER_SYSTEM,
            response_format="text",
            max_retries=3,
            trace_id=str(uuid4()),
        )
    except LLMFailure as exc:
        raise CoverLetterGenerationError(str(exc)) from exc

    return _strip_metadata(response)


def _strip_metadata(response: str) -> str:
    text = response.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("text"):
            text = text[4:].strip()
    return text
