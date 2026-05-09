from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationError, field_validator

from llm.client import LLMFailure, LLMRouter
from llm.prompts import JOB_SCORING_PROMPT, JOB_SCORING_SYSTEM
from resume.safety import ContentSafetyError, sanitize_user_content
from schemas.api_schemas import ResumeProfile, UserPreferences
from scrapers.base import FullJobDetail


class ScoringError(Exception):
    pass


class JobScoreResult(BaseModel):
    total_score: int = Field(ge=0, le=100)
    technical_match: int = Field(ge=0, le=100)
    experience_match: int = Field(ge=0, le=100)
    domain_match: int = Field(ge=0, le=100)
    location_match: int = Field(ge=0, le=100)
    growth_potential: int = Field(ge=0, le=100)
    missing_skills: list[str] = Field(default_factory=list)
    matching_skills: list[str] = Field(default_factory=list)
    score_explanation: str
    recommendation: str

    @field_validator("recommendation")
    @classmethod
    def validate_recommendation(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"APPLY", "SKIP", "STRETCH"}:
            raise ValueError("recommendation must be APPLY, SKIP, or STRETCH")
        return normalized


async def score_job(
    job: FullJobDetail,
    profile: ResumeProfile,
    preferences: UserPreferences,
    llm_router: LLMRouter,
) -> JobScoreResult:
    try:
        safe_title = sanitize_user_content(job.title)[:500]
        safe_company = sanitize_user_content(job.company)[:255]
        safe_description = sanitize_user_content(job.description)[:4000]
    except ContentSafetyError as exc:
        raise ScoringError(f"Unsafe job content rejected: {exc}") from exc

    prompt = JOB_SCORING_PROMPT.format(
        full_name=profile.full_name,
        skills=_profile_skills(profile),
        experience=[f"{exp.company} - {exp.role}" for exp in profile.experience],
        education=[item.model_dump() for item in profile.education],
        target_roles=preferences.target_roles,
        preferred_locations=preferences.preferred_locations,
        work_type=preferences.work_type,
        title=safe_title,
        company=safe_company,
        location=job.location or "",
        job_work_type=job.work_type or "",
        description=safe_description,
    )
    try:
        response = await llm_router.call_with_retry(
            task_type="scan",
            prompt=prompt,
            system=JOB_SCORING_SYSTEM,
            response_format="json",
            max_retries=3,
            trace_id=str(uuid4()),
        )
    except LLMFailure as exc:
        raise ScoringError(str(exc)) from exc

    try:
        payload = _json_payload(response)
        score = JobScoreResult.model_validate(payload)
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
        raise ScoringError(f"Invalid scoring response: {exc}") from exc

    return _fill_skill_gaps(score, profile, job)


def _json_payload(response: str) -> dict[str, Any]:
    text = response.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    return json.loads(text)


def _profile_skills(profile: ResumeProfile) -> dict[str, list[str]]:
    return profile.skills.model_dump()


def _flat_profile_skills(profile: ResumeProfile) -> set[str]:
    skills = profile.skills.model_dump()
    flattened: set[str] = set()
    for values in skills.values():
        flattened.update(str(value).lower() for value in values)
    for project in profile.projects:
        flattened.update(skill.lower() for skill in project.tech_stack)
    for experience in profile.experience:
        flattened.update(skill.lower() for skill in experience.tech_stack)
    return flattened


def _fill_skill_gaps(
    score: JobScoreResult,
    profile: ResumeProfile,
    job: FullJobDetail,
) -> JobScoreResult:
    if score.matching_skills and score.missing_skills:
        return score
    candidate_skills = _flat_profile_skills(profile)
    required = {skill.lower() for skill in job.skills_required}
    matching = sorted(required & candidate_skills)
    missing = sorted(required - candidate_skills)
    if not score.matching_skills:
        score.matching_skills = matching
    if not score.missing_skills:
        score.missing_skills = missing
    return score
