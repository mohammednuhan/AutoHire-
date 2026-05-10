from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from redis.asyncio import Redis

from browser.driver import BrowserDriver
from browser.models import Action, ActionValidationResult, ApplicationResult, ScreenshotResult
from browser.validator import validate_action
from database.models import AgentLog, Application, ApplicationEvent, Job
from database.session import AsyncSessionLocal
from llm.client import LLMRouter
from memory.qa_memory import retrieve_similar_answer
from notifications.telegram import send_health_alert, send_needs_human_alert, send_telegram_message
from storage import data_dir
from websocket import websocket_manager

logger = logging.getLogger("autohire.browser.state_machine")

STOP_KEY = "autohire:stop_requested"
AGENT_STATE_KEY = "autohire:agent_state"


class ApplicationStateMachine:
    """
    Manages a single application's form filling.
    Every state transition is committed to agent_logs before the next action starts.
    """

    async def run(
        self,
        application_id: str,
        action_plan: list[Action],
        driver: BrowserDriver,
        llm_router: LLMRouter,
        trace_id: str,
    ) -> ApplicationResult:
        for action in action_plan:
            await self._set_runtime_status(
                application_id,
                trace_id,
                "running",
                action.field_description,
            )

            if await self._stop_requested():
                await self.persist_state(
                    application_id,
                    trace_id,
                    action.step,
                    "interrupted",
                    action=action,
                )
                await update_application_status(
                    application_id,
                    "interrupted",
                    failure_reason="STOP_REQUESTED",
                )
                return ApplicationResult(status="interrupted", stopped_at_step=action.step)

            if _needs_human_value(action):
                if _needs_human_reason(action) == "SCREENING_QUESTION":
                    cached_answer = await retrieve_similar_answer(action.field_description or "")
                    if cached_answer:
                        data = action.model_dump()
                        data["value"] = cached_answer
                        if str(data.get("option_value") or "").strip().upper() == "NEEDS_HUMAN":
                            data["option_value"] = cached_answer
                        action = Action.model_validate(data)
                    else:
                        reason = _needs_human_reason(action)
                        await self.set_needs_human(
                            application_id=application_id,
                            trace_id=trace_id,
                            reason=reason,
                            field_name=action.field_description,
                            question_text=action.field_description,
                            step=action.step,
                            driver=driver,
                            action=action,
                        )
                        return ApplicationResult(status="needs_human", paused_at_step=action.step)
                else:
                    reason = _needs_human_reason(action)
                    await self.set_needs_human(
                        application_id=application_id,
                        trace_id=trace_id,
                        reason=reason,
                        field_name=action.field_description,
                        question_text=action.field_description,
                        step=action.step,
                        driver=driver,
                        action=action,
                    )
                    return ApplicationResult(status="needs_human", paused_at_step=action.step)

            await self.log_step(
                application_id=application_id,
                trace_id=trace_id,
                step_number=action.step,
                field_name=action.field_description,
                action_type=action.action,
                action_data=action.model_dump(exclude_none=True),
                status="in_progress",
                attempt_number=1,
            )
            await publish_ws_event(
                "BROWSER_ACTION",
                application_id=application_id,
                trace_id=trace_id,
                step=action.step,
                action=action.action,
                field=action.field_description or "",
            )

            result = await self.execute_action(driver, action)
            validation = await validate_action(
                screenshot_bytes=result.screenshot_bytes,
                expected_state=action.expected_state,
                action_description=action.human_description(),
                llm_router=llm_router,
            )
            if not result.success and validation.passed:
                validation = ActionValidationResult(
                    confidence=0.0,
                    passed=False,
                    observation=validation.observation,
                    error_detected=True,
                    error_text=result.error,
                    failure_reason="ACTION_FAILED",
                )
            screenshot_path = await self.save_screenshot(
                application_id,
                action.step,
                result.screenshot_bytes,
                suffix="attempt_1",
            )

            if not validation.passed:
                handled = await self._handle_failed_validation(
                    application_id=application_id,
                    trace_id=trace_id,
                    action=action,
                    driver=driver,
                    llm_router=llm_router,
                    validation=validation,
                    screenshot_path=screenshot_path,
                )
                if handled.status != "continue":
                    return handled
                continue

            await self.log_step(
                application_id=application_id,
                trace_id=trace_id,
                step_number=action.step,
                field_name=action.field_description,
                action_type=action.action,
                action_data=action.model_dump(exclude_none=True),
                status="complete",
                confidence=validation.confidence,
                screenshot_path=screenshot_path,
                attempt_number=1,
            )
            await publish_ws_event(
                "VALIDATION_RESULT",
                application_id=application_id,
                trace_id=trace_id,
                field=action.field_description or "",
                confidence=validation.confidence,
                passed=True,
            )

        await update_application_status(application_id, "ready_to_submit")
        await self._set_runtime_status(application_id, trace_id, "idle", None)
        await publish_ws_event(
            "APPLICATION_SUCCESS",
            application_id=application_id,
            trace_id=trace_id,
            status="ready_to_submit",
        )
        return ApplicationResult(status="ready_to_submit")

    async def execute_action(self, driver: BrowserDriver, action: Action) -> ScreenshotResult:
        if action.selector and action.action in {"fill", "click", "checkbox", "select", "upload"}:
            css_result = await self.try_css_fallback(driver, action)
            if css_result is not None and css_result.success:
                return css_result
        if action.action == "navigate":
            return await driver.navigate(action.url or "")
        if action.action == "fill":
            return await driver.fill_field(action.field_description or "", action.value or "")
        if action.action == "click":
            return await driver.click_element(action.field_description or "")
        if action.action == "checkbox":
            return await driver.click_element(action.field_description or "")
        if action.action == "upload":
            return await driver.upload_file(action.field_description or "", action.file_path or "")
        if action.action == "select":
            return await driver.select_option(
                action.field_description or "",
                action.option_value or action.value or "",
            )
        if action.action == "scroll":
            scroll_page = getattr(driver, "scroll_page", None)
            if scroll_page is not None:
                return await scroll_page(action.value)
            return ScreenshotResult(success=True, screenshot_bytes=await driver.take_screenshot())
        if action.action == "screenshot":
            return ScreenshotResult(success=True, screenshot_bytes=await driver.take_screenshot())
        return ScreenshotResult(
            success=False,
            screenshot_bytes=await driver.take_screenshot(),
            error="Unknown action",
        )

    async def retry_action(
        self,
        driver: BrowserDriver,
        action: Action,
        error_context: str | None,
    ) -> ScreenshotResult:
        logger.info(
            "retrying_browser_action",
            extra={"step": action.step, "action": action.action, "error": error_context},
        )
        return await self.execute_action(driver, action)

    async def try_css_fallback(
        self,
        driver: BrowserDriver,
        action: Action,
    ) -> ScreenshotResult | None:
        fallback = getattr(driver, "css_fallback", None)
        if fallback is None:
            return None
        return await fallback(action)

    async def _handle_failed_validation(
        self,
        application_id: str,
        trace_id: str,
        action: Action,
        driver: BrowserDriver,
        llm_router: LLMRouter,
        validation: ActionValidationResult,
        screenshot_path: str | None,
    ) -> ApplicationResult:
        await self.log_step(
            application_id=application_id,
            trace_id=trace_id,
            step_number=action.step,
            field_name=action.field_description,
            action_type=action.action,
            action_data=action.model_dump(exclude_none=True),
            status="failed_validation",
            confidence=validation.confidence,
            screenshot_path=screenshot_path,
            attempt_number=1,
            error_message=validation.error_text or validation.failure_reason,
        )
        if validation.failure_reason == "CAPTCHA_DETECTED":
            await self.set_needs_human(
                application_id=application_id,
                trace_id=trace_id,
                reason="CAPTCHA_DETECTED",
                field_name=action.field_description,
                confidence=validation.confidence,
                question_text=action.field_description,
                step=action.step,
                driver=driver,
                action=action,
            )
            return ApplicationResult(status="needs_human", paused_at_step=action.step)
        if validation.failure_reason == "LOW_CONFIDENCE":
            await self.set_needs_human(
                application_id=application_id,
                trace_id=trace_id,
                reason="LOW_CONFIDENCE",
                field_name=action.field_description,
                confidence=validation.confidence,
                question_text=action.field_description,
                step=action.step,
                driver=driver,
                action=action,
                screenshot_path=screenshot_path,
            )
            return ApplicationResult(status="needs_human", paused_at_step=action.step)

        retry_result = await self.retry_action(driver, action, validation.error_text)
        retry_validation = await validate_action(
            retry_result.screenshot_bytes,
            action.expected_state,
            action.human_description(),
            llm_router,
        )
        retry_screenshot_path = await self.save_screenshot(
            application_id,
            action.step,
            retry_result.screenshot_bytes,
            suffix="attempt_2",
        )
        if retry_validation.passed:
            await self.log_step(
                application_id=application_id,
                trace_id=trace_id,
                step_number=action.step,
                field_name=action.field_description,
                action_type=action.action,
                action_data=action.model_dump(exclude_none=True),
                status="complete",
                confidence=retry_validation.confidence,
                screenshot_path=retry_screenshot_path,
                attempt_number=2,
            )
            await publish_ws_event(
                "VALIDATION_RESULT",
                application_id=application_id,
                trace_id=trace_id,
                field=action.field_description or "",
                confidence=retry_validation.confidence,
                passed=True,
            )
            return ApplicationResult(status="continue")

        css_result = await self.try_css_fallback(driver, action)
        if css_result is not None:
            css_validation = await validate_action(
                css_result.screenshot_bytes,
                action.expected_state,
                action.human_description(),
                llm_router,
            )
            css_screenshot_path = await self.save_screenshot(
                application_id,
                action.step,
                css_result.screenshot_bytes,
                suffix="css_fallback",
            )
            if css_validation.passed:
                await self.log_step(
                    application_id=application_id,
                    trace_id=trace_id,
                    step_number=action.step,
                    field_name=action.field_description,
                    action_type=action.action,
                    action_data=action.model_dump(exclude_none=True),
                    status="complete",
                    confidence=css_validation.confidence,
                    screenshot_path=css_screenshot_path,
                    attempt_number=3,
                )
                await publish_ws_event(
                    "VALIDATION_RESULT",
                    application_id=application_id,
                    trace_id=trace_id,
                    field=action.field_description or "",
                    confidence=css_validation.confidence,
                    passed=True,
                )
                return ApplicationResult(status="continue")
            retry_validation = css_validation
            retry_screenshot_path = css_screenshot_path

        await self.set_needs_human(
            application_id=application_id,
            trace_id=trace_id,
            reason=retry_validation.failure_reason or "LOW_CONFIDENCE",
            field_name=action.field_description,
            confidence=retry_validation.confidence,
            question_text=action.field_description,
            step=action.step,
            driver=driver,
            action=action,
            screenshot_path=retry_screenshot_path,
        )
        return ApplicationResult(status="needs_human", paused_at_step=action.step)

    async def persist_state(
        self,
        application_id: str,
        trace_id: str,
        step: int,
        status: str,
        action: Action | None = None,
    ) -> None:
        await self.log_step(
            application_id=application_id,
            trace_id=trace_id,
            step_number=step,
            field_name=action.field_description if action else None,
            action_type=action.action if action else None,
            action_data=action.model_dump(exclude_none=True) if action else None,
            status=status,
        )

    async def log_step(
        self,
        application_id: str,
        trace_id: str,
        step_number: int,
        field_name: str | None,
        action_type: str | None,
        status: str,
        action_data: dict[str, Any] | None = None,
        confidence: float | None = None,
        screenshot_path: str | None = None,
        attempt_number: int = 1,
        error_message: str | None = None,
    ) -> None:
        async with AsyncSessionLocal() as db:
            db.add(
                AgentLog(
                    application_id=application_id,
                    trace_id=trace_id,
                    step_number=step_number,
                    field_name=field_name,
                    action_type=action_type,
                    action_data=action_data,
                    confidence=confidence,
                    status=status,
                    screenshot_path=screenshot_path,
                    attempt_number=attempt_number,
                    error_message=error_message,
                )
            )
            await db.commit()

    async def set_needs_human(
        self,
        application_id: str,
        trace_id: str,
        reason: str,
        field_name: str | None = None,
        confidence: float | None = None,
        question_text: str | None = None,
        step: int | None = None,
        driver: BrowserDriver | None = None,
        action: Action | None = None,
        screenshot_path: str | None = None,
    ) -> None:
        if screenshot_path is None and driver is not None:
            try:
                screenshot_bytes = await driver.take_screenshot()
            except Exception:
                screenshot_bytes = None
            screenshot_path = await self.save_screenshot(application_id, step, screenshot_bytes)

        await update_application_status(application_id, "needs_human", failure_reason=reason)
        if step is not None:
            await self.log_step(
                application_id=application_id,
                trace_id=trace_id,
                step_number=step,
                field_name=field_name,
                action_type=action.action if action else None,
                action_data=action.model_dump(exclude_none=True) if action else None,
                status="needs_human",
                confidence=confidence,
                screenshot_path=screenshot_path,
                error_message=reason,
            )

        await self._set_runtime_status(
            application_id,
            trace_id,
            "paused",
            field_name,
            {"reason": reason},
        )
        application, job = await _load_application_and_job(application_id)
        await publish_ws_event(
            "NEEDS_HUMAN",
            application_id=application_id,
            trace_id=trace_id,
            reason=reason,
            field_name=field_name,
            confidence=confidence,
            question_text=question_text,
            screenshot_url=(
                f"/api/applications/{application_id}/screenshots/{step}" if step else None
            ),
            screenshot_path=screenshot_path,
            expires_at=(datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
            company=job.company if job else None,
            role=job.title if job else None,
        )
        await send_needs_human_alert(
            application_id=application_id,
            company=job.company if job else "Unknown",
            role=job.title if job else "Unknown",
            field_name=field_name or "Review",
            reason=reason,
            screenshot_available=bool(screenshot_path),
        )

    async def save_screenshot(
        self,
        application_id: str,
        step: int | None,
        screenshot_bytes: bytes | None,
        suffix: str | None = None,
    ) -> str | None:
        if not screenshot_bytes:
            return None
        output_dir = data_dir() / "applications" / application_id / "screenshots"
        output_dir.mkdir(parents=True, exist_ok=True)
        step_name = f"step_{step}" if step is not None else "needs_human"
        filename = f"{step_name}_{suffix}.png" if suffix else f"{step_name}.png"
        path = output_dir / filename
        path.write_bytes(screenshot_bytes)
        return str(path)

    async def _stop_requested(self) -> bool:
        redis = _redis()
        try:
            return bool(await redis.get(STOP_KEY))
        finally:
            await redis.aclose()

    async def _set_runtime_status(
        self,
        application_id: str | None,
        trace_id: str | None,
        status: str,
        current_field: str | None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        redis = _redis()
        _application, job = (
            await _load_application_and_job(application_id) if application_id else (None, None)
        )
        payload = {
            "status": status,
            "current_application_id": application_id,
            "current_company": job.company if job else None,
            "trace_id": trace_id,
            "current_field": current_field,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "extra": extra or {},
        }
        try:
            await redis.set(AGENT_STATE_KEY, json.dumps(payload), ex=60 * 60)
        finally:
            await redis.aclose()


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
        now = datetime.now(timezone.utc)
        if status == "agent_processing" and application.started_at is None:
            application.started_at = now
        if status == "submitted":
            application.submitted_at = now
            application.completed_at = now
        await db.commit()


async def publish_ws_event(
    event_type: str,
    application_id: str | None = None,
    trace_id: str | None = None,
    **event_data: Any,
) -> None:
    payload = {
        "event": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **event_data,
    }
    if application_id is not None:
        payload["application_id"] = application_id
    if trace_id is not None:
        payload["trace_id"] = trace_id
    async with AsyncSessionLocal() as db:
        db.add(
            ApplicationEvent(
                application_id=application_id,
                trace_id=trace_id,
                event_type=event_type,
                event_data=payload,
            )
        )
        await db.commit()
    await websocket_manager.publish(payload)
    if event_type == "ERROR":
        await send_health_alert(str(event_data.get("error_code", "ERROR")), str(event_data.get("message", "")))


async def send_telegram_alert(message: str) -> None:
    await send_telegram_message(message)


async def runtime_status() -> dict[str, Any]:
    redis = _redis()
    try:
        raw = await redis.get(AGENT_STATE_KEY)
        stop_requested = bool(await redis.get(STOP_KEY))
    finally:
        await redis.aclose()
    status = json.loads(raw) if raw else {"status": "idle"}
    status["stop_requested"] = stop_requested
    return status


async def request_stop(ttl_seconds: int = 60 * 60) -> None:
    redis = _redis()
    try:
        await redis.set(STOP_KEY, "1", ex=ttl_seconds)
    finally:
        await redis.aclose()


def _redis() -> Redis:
    return Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)


def _needs_human_value(action: Action) -> bool:
    values = [action.value, action.option_value]
    return any(str(value or "").strip().upper() == "NEEDS_HUMAN" for value in values)


def _needs_human_reason(action: Action) -> str:
    field = (action.field_description or "").lower()
    if "salary" in field or "ctc" in field or "compensation" in field:
        return "SALARY_QUESTION"
    return "SCREENING_QUESTION"


async def _load_application_and_job(application_id: str) -> tuple[Application | None, Job | None]:
    async with AsyncSessionLocal() as db:
        application = await db.get(Application, application_id)
        if application is None:
            return None, None
        job = await db.get(Job, application.job_id)
        return application, job
