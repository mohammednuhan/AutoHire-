from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from database.models import Application, Job
from database.session import AsyncSessionLocal
from llm.client import LLMRouter
from notifications.telegram import send_telegram_message

logger = logging.getLogger("autohire.notifications.followup")

_followup_scheduler: AsyncIOScheduler | None = None


async def mark_ghosted_and_draft_followups(llm_router: LLMRouter | None = None) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    router = llm_router or LLMRouter()
    drafted = 0
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(Application, Job)
                .join(Job, Job.id == Application.job_id)
                .where(Application.status == "submitted", Application.submitted_at < cutoff)
            )
        ).all()
        for application, job in rows:
            draft = await _draft_followup(router, job)
            application.status = "ghosted"
            application.notes = _append_note(application.notes, draft)
            drafted += 1
        await db.commit()

    if drafted:
        await send_telegram_message(
            f"{drafted} applications are 14+ days old with no response. "
            "Follow-up drafts are ready to review."
        )
    logger.info("followup_check_completed", extra={"drafted": drafted})
    return drafted


async def _draft_followup(llm_router: LLMRouter, job: Job) -> str:
    prompt = (
        "Draft a concise follow-up email for a submitted job application. "
        "Do not claim anything beyond checking in politely.\n\n"
        f"Company: {job.company}\nRole: {job.title}\n"
        "Return only the email body."
    )
    return await llm_router.call_with_retry(
        task_type="reason",
        prompt=prompt,
        system="You write concise professional follow-up emails.",
        max_retries=2,
        trace_id=str(uuid4()),
    )


def _append_note(existing: str | None, draft: str) -> str:
    marker = f"\n\n--- Follow-up draft {datetime.now(timezone.utc).date().isoformat()} ---\n"
    return f"{existing or ''}{marker}{draft.strip()}".strip()


def start_followup_scheduler() -> None:
    global _followup_scheduler
    if _followup_scheduler and _followup_scheduler.running:
        return
    timezone_name = os.getenv("USER_TIMEZONE", "Asia/Kolkata")
    _followup_scheduler = AsyncIOScheduler(timezone=timezone_name)
    _followup_scheduler.add_job(
        mark_ghosted_and_draft_followups,
        trigger=CronTrigger(day_of_week="mon", hour=9, minute=0, timezone=timezone_name),
        id="weekly_followups",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    _followup_scheduler.start()


async def stop_followup_scheduler() -> None:
    global _followup_scheduler
    if _followup_scheduler and _followup_scheduler.running:
        _followup_scheduler.shutdown(wait=False)
    _followup_scheduler = None
