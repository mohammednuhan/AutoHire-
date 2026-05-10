from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import delete, select

from database.models import AgentLog, ApplicationEvent, CompanyCache, Job
from database.session import AsyncSessionLocal

logger = logging.getLogger("autohire.maintenance.cleanup")

_cleanup_scheduler: AsyncIOScheduler | None = None


async def run_weekly_cleanup() -> dict[str, int]:
    now = datetime.now(timezone.utc)
    screenshot_cutoff = now - timedelta(days=90)
    event_cutoff = now - timedelta(days=365)
    expired_job_cutoff = now - timedelta(days=90)
    deleted_files = 0

    async with AsyncSessionLocal() as db:
        old_logs = (
            await db.execute(
                select(AgentLog).where(
                    AgentLog.screenshot_path.is_not(None),
                    AgentLog.created_at < screenshot_cutoff,
                )
            )
        ).scalars().all()
        for log in old_logs:
            path = Path(log.screenshot_path or "")
            if path.exists():
                path.unlink(missing_ok=True)
                deleted_files += 1
            log.screenshot_path = None

        events_deleted = (
            await db.execute(delete(ApplicationEvent).where(ApplicationEvent.created_at < event_cutoff))
        ).rowcount or 0
        cache_deleted = (
            await db.execute(delete(CompanyCache).where(CompanyCache.expires_at < now))
        ).rowcount or 0
        jobs_deleted = (
            await db.execute(
                delete(Job).where(Job.status == "expired", Job.scraped_at < expired_job_cutoff)
            )
        ).rowcount or 0
        await db.commit()

    result = {
        "screenshot_files_deleted": deleted_files,
        "screenshot_paths_cleared": len(old_logs),
        "application_events_deleted": int(events_deleted),
        "company_cache_deleted": int(cache_deleted),
        "expired_jobs_deleted": int(jobs_deleted),
    }
    logger.info("cleanup_completed", extra=result)
    return result


def start_cleanup_scheduler() -> None:
    global _cleanup_scheduler
    if _cleanup_scheduler and _cleanup_scheduler.running:
        return
    timezone_name = os.getenv("USER_TIMEZONE", "Asia/Kolkata")
    _cleanup_scheduler = AsyncIOScheduler(timezone=timezone_name)
    _cleanup_scheduler.add_job(
        run_weekly_cleanup,
        trigger=CronTrigger(day_of_week="sun", hour=3, minute=0, timezone=timezone_name),
        id="weekly_cleanup",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    _cleanup_scheduler.start()


async def stop_cleanup_scheduler() -> None:
    global _cleanup_scheduler
    if _cleanup_scheduler and _cleanup_scheduler.running:
        _cleanup_scheduler.shutdown(wait=False)
    _cleanup_scheduler = None
