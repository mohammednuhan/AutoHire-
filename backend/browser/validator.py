from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from browser.models import ActionValidationResult
from cover_letter.text_utils import json_payload
from llm.client import LLMFailure, LLMRouter
from llm.prompts import ACTION_VALIDATION_PROMPT, ACTION_VALIDATION_SYSTEM

CONFIDENCE_THRESHOLD = 0.80


async def validate_action(
    screenshot_bytes: bytes,
    expected_state: str,
    action_description: str,
    llm_router: LLMRouter,
) -> ActionValidationResult:
    if not screenshot_bytes:
        return ActionValidationResult(
            confidence=0.0,
            passed=False,
            observation="No screenshot was captured after the action.",
            error_detected=True,
            error_text="Screenshot missing",
            failure_reason="SCREENSHOT_MISSING",
        )

    prompt = ACTION_VALIDATION_PROMPT.format(
        action_description=action_description,
        expected_state=expected_state,
    )
    try:
        response = await llm_router.call_vision_with_retry(
            task_type="reason",
            prompt=prompt,
            image_bytes=screenshot_bytes,
            system=ACTION_VALIDATION_SYSTEM,
            response_format="json",
            max_retries=3,
            trace_id=str(uuid4()),
        )
        payload = json_payload(response)
        return _validation_from_payload(payload)
    except (LLMFailure, ValueError, TypeError, KeyError) as exc:
        return ActionValidationResult(
            confidence=0.0,
            passed=False,
            observation=f"Validator failed: {exc}",
            error_detected=True,
            error_text=str(exc),
            failure_reason="VALIDATOR_FAILED",
        )


def _validation_from_payload(payload: dict[str, Any]) -> ActionValidationResult:
    confidence = _confidence(payload.get("confidence"))
    llm_passed = _as_bool(payload.get("passed", False))
    error_detected = _as_bool(payload.get("error_detected", False))
    observation = str(payload.get("observation") or "").strip() or "No observation returned."
    error_text = _optional_text(payload.get("error_text"))
    blocking_element = _optional_text(payload.get("blocking_element"))
    failure_reason = _failure_reason(
        confidence=confidence,
        llm_passed=llm_passed,
        error_detected=error_detected,
        observation=observation,
        error_text=error_text,
        blocking_element=blocking_element,
    )
    return ActionValidationResult(
        confidence=confidence,
        passed=failure_reason is None,
        observation=observation,
        error_detected=error_detected,
        error_text=error_text,
        blocking_element=blocking_element,
        failure_reason=failure_reason,
    )


def _failure_reason(
    confidence: float,
    llm_passed: bool,
    error_detected: bool,
    observation: str,
    error_text: str | None,
    blocking_element: str | None,
) -> str | None:
    combined = " ".join(part for part in [observation, error_text, blocking_element] if part)
    normalized = combined.lower()
    if re.search(r"captcha|recaptcha|hcaptcha|verify you are human", normalized):
        return "CAPTCHA_DETECTED"
    if re.search(r"session expired|logged out|sign in|login required", normalized):
        return "SESSION_EXPIRED"
    if error_detected or error_text:
        return "ERROR_MESSAGE"
    if blocking_element:
        return "BLOCKING_ELEMENT"
    if not llm_passed or confidence < CONFIDENCE_THRESHOLD:
        return "LOW_CONFIDENCE"
    return None


def _confidence(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
        return value.strip().lower() == "true"
    return bool(value)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "null":
        return None
    return text
