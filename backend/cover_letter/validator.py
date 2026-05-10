from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from cover_letter.models import ValidationResult
from cover_letter.text_utils import (
    banned_phrase_hits,
    json_payload,
    opens_with_i,
    paragraphs,
    word_count,
)
from database.models import Job
from llm.client import LLMFailure, LLMRouter
from llm.prompts import COVER_LETTER_VALIDATION_PROMPT, COVER_LETTER_VALIDATION_SYSTEM
from resume.formatting import format_full_profile
from schemas.api_schemas import ResumeProfile


class CoverLetterValidationError(Exception):
    pass


async def validate_cover_letter(
    cover_letter: str,
    profile: ResumeProfile,
    job: Job,
    llm_router: LLMRouter,
) -> ValidationResult:
    prompt = COVER_LETTER_VALIDATION_PROMPT.format(
        full_profile=format_full_profile(profile),
        cover_letter=cover_letter,
    )
    local_word_count = word_count(cover_letter)

    try:
        response = await llm_router.call_with_retry(
            task_type="reason",
            prompt=prompt,
            system=COVER_LETTER_VALIDATION_SYSTEM,
            response_format="json",
            max_retries=3,
            trace_id=str(uuid4()),
        )
        payload = json_payload(response)
    except (LLMFailure, ValueError) as exc:
        return ValidationResult(
            passed=False,
            unsupported_claims=[f"Validator failed for job {job.id}: {exc}"],
            word_count=local_word_count,
            failure_reason="HALLUCINATED_CLAIMS",
        )

    try:
        all_claims_supported = _as_bool(payload["all_claims_supported"])
        unsupported_claims = _unsupported_claims(payload.get("unsupported_claims", []))
    except (KeyError, TypeError, ValidationError, ValueError) as exc:
        return ValidationResult(
            passed=False,
            unsupported_claims=[f"Validator returned invalid JSON for job {job.id}: {exc}"],
            word_count=local_word_count,
            failure_reason="HALLUCINATED_CLAIMS",
        )

    local_violations = _local_rule_violations(cover_letter)
    if unsupported_claims:
        all_claims_supported = False
    unsupported_claims.extend(local_violations)

    failure_reason = _failure_reason(
        all_claims_supported=all_claims_supported,
        local_word_count=local_word_count,
        local_violations=local_violations,
    )
    return ValidationResult(
        passed=failure_reason is None,
        unsupported_claims=unsupported_claims,
        word_count=local_word_count,
        failure_reason=failure_reason,
    )


def _unsupported_claims(raw_claims: Any) -> list[str]:
    claims: list[str] = []
    if not isinstance(raw_claims, list):
        return claims
    for item in raw_claims:
        if isinstance(item, dict):
            claim = str(item.get("claim", "")).strip()
            reason = str(item.get("reason", "")).strip()
            if claim and reason:
                claims.append(f"{claim} - {reason}")
            elif claim:
                claims.append(claim)
        elif item:
            claims.append(str(item))
    return claims


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
        return value.strip().lower() == "true"
    raise ValueError("all_claims_supported must be a boolean")


def _local_rule_violations(cover_letter: str) -> list[str]:
    violations: list[str] = []
    paragraph_count = len(paragraphs(cover_letter))
    if paragraph_count != 3:
        violations.append(f"Cover letter has {paragraph_count} paragraphs; exactly 3 are required.")
    banned = banned_phrase_hits(cover_letter)
    if banned:
        violations.append(f"Cover letter contains banned phrases: {', '.join(banned)}.")
    if opens_with_i(cover_letter):
        violations.append("Cover letter opens with 'I', which is not allowed.")
    return violations


def _failure_reason(
    all_claims_supported: bool,
    local_word_count: int,
    local_violations: list[str],
) -> str | None:
    if not all_claims_supported:
        return "HALLUCINATED_CLAIMS"
    if local_word_count < 200:
        return "TOO_SHORT"
    if local_word_count > 300:
        return "TOO_LONG"
    if local_violations:
        return "HALLUCINATED_CLAIMS"
    return None
