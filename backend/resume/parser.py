from __future__ import annotations

import json
from uuid import uuid4

from pydantic import ValidationError

from llm.client import LLMRouter
from llm.prompts import RESUME_EXTRACTION_PROMPT, RESUME_EXTRACTION_SYSTEM
from resume.safety import sanitize_user_content
from schemas.api_schemas import ResumeProfile


class ParseError(Exception):
    def __init__(self, message: str, missing_fields: list[str] | None = None) -> None:
        super().__init__(message)
        self.missing_fields = missing_fields or []


def _missing_required_fields(profile: ResumeProfile) -> list[str]:
    missing = []
    if not profile.full_name:
        missing.append("full_name")
    if not profile.email:
        missing.append("email")
    if not profile.skills.languages:
        missing.append("skills.languages")
    return missing


async def parse_resume(raw_text: str, llm_router: LLMRouter) -> ResumeProfile:
    safe_text = sanitize_user_content(raw_text)
    prompt = RESUME_EXTRACTION_PROMPT.format(raw_text=safe_text)
    trace_id = str(uuid4())
    last_error = ""
    last_missing: list[str] = []

    for _ in range(3):
        try:
            response = await llm_router.call_with_retry(
                task_type="extract",
                prompt=prompt,
                system=RESUME_EXTRACTION_SYSTEM,
                response_format="json",
                max_retries=1,
                trace_id=trace_id,
            )
            payload = json.loads(response)
            profile = ResumeProfile.model_validate(payload)
            missing = _missing_required_fields(profile)
            if missing:
                raise ParseError(f"missing required fields: {missing}", missing)
            return profile
        except (json.JSONDecodeError, ValidationError, ParseError) as exc:
            last_error = str(exc)
            if isinstance(exc, ParseError) and exc.missing_fields:
                last_missing = exc.missing_fields

    raise ParseError(last_error or "Resume extraction failed", last_missing)
