from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from pydantic import BaseModel
from sqlalchemy import func, select

from api.websocket import publish_ws_event
from database.models import Application, Job, JobScore
from database.session import AsyncSessionLocal
from notifications.telegram import send_morning_digest

logger = logging.getLogger("autohire.notifications.digest")

_digest_scheduler: AsyncIOScheduler | None = None


class MorningSummary(BaseModel):
    date: str
    jobs_scanned: int
    new_high_score_jobs: int
    apps_attempted: int
    apps_completed: int
    apps_needs_review: int


async def generate_and_send_morning_digest() -> MorningSummary:
    """
    Runs at 8 AM every day.
    Generates the previous 24-hour summary even if no scan ran.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    today_str = datetime.now(timezone.utc).date().isoformat()

    summary = MorningSummary(
        date=today_str,
        jobs_scanned=await count_jobs_scraped_since(since),
        new_high_score_jobs=await count_high_score_jobs(since=since, threshold=85),
        apps_attempted=await count_applications(since=since),
        apps_completed=await count_applications_by_status("submitted", since=since),
        apps_needs_review=await count_applications_by_status("ready_to_submit"),
    )

    await publish_ws_event("MORNING_SUMMARY", **summary.model_dump())
    await send_morning_digest(summary)
    return summary


async def count_jobs_scraped_since(since: datetime) -> int:
    async with AsyncSessionLocal() as db:
        count = await db.scalar(select(func.count()).select_from(Job).where(Job.scraped_at >= since))
        return int(count or 0)


async def count_high_score_jobs(since: datetime, threshold: int = 85) -> int:
    async with AsyncSessionLocal() as db:
        count = await db.scalar(
            select(func.count())
            .select_from(JobScore)
            .where(JobScore.scored_at >= since, JobScore.total_score >= threshold)
        )
        return int(count or 0)


async def count_applications(since: datetime) -> int:
    async with AsyncSessionLocal() as db:
        count = await db.scalar(
            select(func.count()).select_from(Application).where(Application.queued_at >= since)
        )
        return int(count or 0)


async def count_applications_by_status(status: str, since: datetime | None = None) -> int:
    conditions = [Application.status == status]
    if since is not None:
        if status == "submitted":
            conditions.append(Application.submitted_at >= since)
        else:
            conditions.append(Application.queued_at >= since)

    async with AsyncSessionLocal() as db:
        count = await db.scalar(select(func.count()).select_from(Application).where(*conditions))
        return int(count or 0)


def start_digest_scheduler() -> None:
    global _digest_scheduler
    if _digest_scheduler and _digest_scheduler.running:
        return

    timezone_name = os.getenv("USER_TIMEZONE", "Asia/Kolkata")
    cron_expr = os.getenv("MORNING_DIGEST_CRON", "0 8 * * *")
    trigger = CronTrigger.from_crontab(cron_expr, timezone=timezone_name)
    _digest_scheduler = AsyncIOScheduler(timezone=timezone_name)
    _digest_scheduler.add_job(
        generate_and_send_morning_digest,
        trigger=trigger,
        id="morning_digest",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    _digest_scheduler.start()
    logger.info("morning_digest_scheduler_started", extra={"cron": cron_expr})


async def stop_digest_scheduler() -> None:
    global _digest_scheduler
    if _digest_scheduler and _digest_scheduler.running:
        _digest_scheduler.shutdown(wait=False)
        logger.info("morning_digest_scheduler_stopped")
    _digest_scheduler = None
