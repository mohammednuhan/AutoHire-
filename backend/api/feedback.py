from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, File, Form, UploadFile

from api.auth import get_current_user
from database.models import User
from storage import data_dir

router = APIRouter(tags=["feedback"])


@router.post("/api/feedback", response_model=dict[str, str])
async def create_feedback(
    current_user: Annotated[User, Depends(get_current_user)],
    application_id: Annotated[str | None, Form()] = None,
    trace_id: Annotated[str | None, Form()] = None,
    message: Annotated[str, Form()] = "",
    screenshot: Annotated[UploadFile | None, File()] = None,
) -> dict[str, str]:
    attachment_path: str | None = None
    if screenshot is not None and screenshot.filename:
        output_dir = data_dir() / "feedback_uploads"
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{screenshot.filename}"
        path.write_bytes(await screenshot.read())
        attachment_path = str(path)

    token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPO")
    if token and repo:
        issue_url = await _create_github_issue(
            token=token,
            repo=repo,
            message=message,
            application_id=application_id,
            trace_id=trace_id,
            attachment_path=attachment_path,
            username=current_user.username,
        )
        return {"status": "github_issue_created", "url": issue_url}

    feedback_path = data_dir() / "feedback.jsonl"
    record = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "user": current_user.username,
        "application_id": application_id,
        "trace_id": trace_id,
        "message": message,
        "screenshot_path": attachment_path,
    }
    with feedback_path.open("a", encoding="utf-8") as output:
        output.write(json.dumps(record) + "\n")
    return {"status": "saved_locally", "path": str(feedback_path)}


async def _create_github_issue(
    token: str,
    repo: str,
    message: str,
    application_id: str | None,
    trace_id: str | None,
    attachment_path: str | None,
    username: str,
) -> str:
    body = (
        f"User: {username}\n\n"
        f"Application ID: {application_id or 'n/a'}\n"
        f"Trace ID: {trace_id or 'n/a'}\n"
        f"Screenshot: {attachment_path or 'not attached'}\n\n"
        f"Feedback:\n{message}"
    )
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            f"https://api.github.com/repos/{repo}/issues",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
            json={"title": "AutoHire user feedback", "body": body, "labels": ["feedback"]},
        )
        response.raise_for_status()
        return str(response.json()["html_url"])
