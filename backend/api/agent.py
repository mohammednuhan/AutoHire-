from __future__ import annotations

import asyncio
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from agent.applicant import (
    load_application_by_trace_id,
    resume_application_after_human,
    submit_application,
)
from api.auth import get_current_user
from browser.state_machine import (
    publish_ws_event,
    request_stop,
    runtime_status,
    update_application_status,
)
from database.models import User
from llm.client import LLMRouter
from storage import data_dir

router = APIRouter(tags=["agent"])
logger = logging.getLogger("autohire.api.agent")


class HumanApproveRequest(BaseModel):
    field_name: str
    answer: str


def api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": code, "message": message})


def _start_background(coro: Any) -> None:
    task = asyncio.create_task(coro)
    task.add_done_callback(_log_background_result)


def _log_background_result(task: asyncio.Task[object]) -> None:
    try:
        task.result()
    except Exception:
        logger.exception("agent_background_task_failed")


@router.post("/api/applications/{application_id}/submit", response_model=dict[str, str])
async def submit_prepared_application(
    application_id: str,
    _current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    try:
        result = await submit_application(application_id, LLMRouter())
    except ValueError as exc:
        raise api_error(404, "NOT_FOUND", str(exc)) from exc
    return {"application_id": application_id, "status": result.status}


@router.post("/api/needs-human/{trace_id}/approve", response_model=dict[str, str])
async def approve_needs_human(
    trace_id: str,
    payload: HumanApproveRequest,
    _current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    try:
        application = await load_application_by_trace_id(trace_id)
        _start_background(
            resume_application_after_human(
                trace_id=trace_id,
                field_name=payload.field_name,
                answer=payload.answer,
                llm_router=LLMRouter(),
            )
        )
    except ValueError as exc:
        raise api_error(404, "NOT_FOUND", str(exc)) from exc
    return {"trace_id": trace_id, "application_id": application.id, "status": "resuming"}


@router.post("/api/needs-human/{trace_id}/skip", response_model=dict[str, str])
async def skip_needs_human(
    trace_id: str,
    _current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    try:
        application = await load_application_by_trace_id(trace_id)
    except ValueError as exc:
        raise api_error(404, "NOT_FOUND", str(exc)) from exc
    await update_application_status(application.id, "skipped")
    await publish_ws_event(
        "APPLICATION_FAILED",
        application_id=application.id,
        trace_id=trace_id,
        reason="USER_SKIPPED",
        step=None,
    )
    return {"trace_id": trace_id, "application_id": application.id, "status": "skipped"}


@router.post("/api/agent/stop", response_model=dict[str, str])
async def stop_agent(
    _current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    await request_stop(ttl_seconds=60 * 60)
    await publish_ws_event(
        "AGENT_STATUS",
        status="idle",
        stop_requested=True,
        current_application_id=None,
        current_company=None,
        current_field=None,
    )
    return {
        "status": "stop_requested",
        "message": "Agent will stop after completing the current field.",
    }


@router.get("/api/agent/status", response_model=dict[str, object])
async def get_agent_status(
    _current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    status = await runtime_status()
    return {
        "status": status.get("status", "idle"),
        "current_application_id": status.get("current_application_id"),
        "current_company": status.get("current_company"),
        "current_field": status.get("current_field"),
        "trace_id": status.get("trace_id"),
        "stop_requested": bool(status.get("stop_requested")),
    }


@router.get("/api/applications/{application_id}/screenshots/{step}")
async def get_application_screenshot(
    application_id: str,
    step: int,
    _current_user: Annotated[User, Depends(get_current_user)],
) -> FileResponse:
    screenshot_dir = data_dir() / "applications" / application_id / "screenshots"
    matches = sorted(
        screenshot_dir.glob(f"step_{step}*.png"),
        key=lambda path: path.stat().st_mtime,
    )
    if not matches:
        raise api_error(404, "NOT_FOUND", "Screenshot not found")
    return FileResponse(str(matches[-1]), media_type="image/png")
