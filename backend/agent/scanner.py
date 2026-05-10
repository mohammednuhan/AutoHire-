from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from agent.applicant import run_application
from agent.preparer import prepare_application
from database.models import Application, ApplicationEvent, Job, JobScore, Resume, Task, UserPreference
from database.session import AsyncSessionLocal, engine
from llm.client import LLMRouter
from notifications.telegram import send_health_alert, send_high_score_alert
from schemas.api_schemas import ResumeProfile, UserPreferences
from scoring.filter import apply_filters
from scoring.scorer import ScoringError, score_job
from scrapers import (
    CareerPageScraper,
    CutshortScraper,
    FounditScraper,
    FullJobDetail,
    InternshalaScraper,
    NaukriScraper,
    WellfoundScraper,
)
from scrapers.base import DailyScrapeLimitExceeded, ScraperStopped, job_content_hash
from websocket import websocket_manager

logger = logging.getLogger("autohire.agent.scanner")

SCAN_LOCK_KEY = "autohire:scan_lock"
SCAN_LOCK_TTL_SECONDS = 2 * 60 * 60
SUPPORTED_SCRAPERS = {
    "wellfound": WellfoundScraper,
    "internshala": InternshalaScraper,
    "career_page": CareerPageScraper,
    "career_pages": CareerPageScraper,
    "naukri": NaukriScraper,
    "foundit": FounditScraper,
    "cutshort": CutshortScraper,
}

_scheduler: AsyncIOScheduler | None = None


async def run_scan(
    task_id: str,
    boards: list[str] | None = None,
    user_id: str | None = None,
    task_type: str = "on_demand_scan",
    scan_lock_token: str | None = None,
) -> None:
    started_at = datetime.now(timezone.utc)
    lock_token = scan_lock_token or str(uuid4())
    redis: Redis | None = None
    lock_acquired = scan_lock_token is not None
    heartbeat_task: asyncio.Task[None] | None = None
    jobs_found = 0
    apps_attempted = 0

    async with AsyncSessionLocal() as db:
        task = await _create_or_mark_task_running(db, task_id, task_type, started_at)
        if lock_acquired:
            redis = _redis()
        guard = await _run_guard()
        if guard is not None:
            try:
                await _fail_task(db, task, guard["message"])
            except Exception as exc:
                logger.info("task_fail_update_failed", extra={"task_id": task_id, "error": str(exc)})
            await _publish_event(db, guard["event"])
            await send_health_alert("RunGuard", guard["message"])
            return

        if redis is None:
            redis = _redis()
        if not lock_acquired:
            lock_acquired = bool(
                await redis.set(SCAN_LOCK_KEY, lock_token, nx=True, ex=SCAN_LOCK_TTL_SECONDS)
            )
        if not lock_acquired:
            logger.info("scan_already_running", extra={"task_id": task_id})
            task.status = "completed"
            task.completed_at = datetime.now(timezone.utc)
            task.result_summary = "Scan already running"
            await db.commit()
            return
        heartbeat_task = asyncio.create_task(_heartbeat_lock(redis, lock_token))

        try:
            resume, profile, preferences = await _load_profile_and_preferences(db, user_id)
            selected_boards = _selected_boards(boards, preferences)
            await _publish_event(
                db,
                {
                    "event": "RUN_STARTED",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "task_id": task_id,
                    "boards": selected_boards,
                },
            )

            llm_router = LLMRouter()
            for board in selected_boards:
                scraper_cls = SUPPORTED_SCRAPERS.get(board)
                if scraper_cls is None:
                    logger.info("unknown_board_skipped", extra={"board": board})
                    continue
                scraper = scraper_cls()
                target_roles = preferences.target_roles or ["software engineer"]
                search_locations = preferences.preferred_locations or [profile.location or "India"]
                for role in target_roles:
                    for location in search_locations:
                        listings = await scraper.scrape_listings([role], location, max_results=50)
                        for listing in listings:
                            filter_result = await apply_filters(listing, preferences, db)
                            if not filter_result.passed:
                                logger.info(
                                    "job_filtered",
                                    extra={
                                        "board": board,
                                        "reason": filter_result.reason,
                                        "matched": filter_result.matched,
                                        "title": listing.title,
                                        "company": listing.company,
                                    },
                                )
                                continue
                            try:
                                detail = await scraper.extract_job_detail(listing)
                            except (DailyScrapeLimitExceeded, ScraperStopped) as exc:
                                logger.warning(
                                    "scraper_stopped",
                                    extra={"board": board, "reason": str(exc)},
                                )
                                break
                            except Exception as exc:
                                logger.info(
                                    "job_detail_failed",
                                    extra={
                                        "board": board,
                                        "url": listing.url,
                                        "error": str(exc),
                                    },
                                )
                                continue

                            inserted = await _insert_job_if_new(db, scraper.board_name, detail)
                            if inserted is None:
                                continue
                            job = inserted
                            try:
                                score = await score_job(detail, profile, preferences, llm_router)
                            except ScoringError as exc:
                                await db.delete(job)
                                await db.commit()
                                logger.warning(
                                    "job_scoring_failed",
                                    extra={"job_id": job.id, "error": str(exc)},
                                )
                                continue
                            jobs_found += 1

                            score_row = JobScore(
                                job_id=job.id,
                                resume_id=resume.id,
                                total_score=score.total_score,
                                technical_match=score.technical_match,
                                experience_match=score.experience_match,
                                domain_match=score.domain_match,
                                location_match=score.location_match,
                                growth_potential=score.growth_potential,
                                missing_skills=score.missing_skills,
                                matching_skills=score.matching_skills,
                                score_explanation=score.score_explanation,
                                recommendation=score.recommendation,
                            )
                            db.add(score_row)
                            application = None
                            if score.total_score < preferences.score_threshold:
                                job.status = "skipped"
                            else:
                                job.status = "queued"
                                application = await _ensure_application(db, job, resume, preferences)
                                apps_attempted += 1
                            await db.commit()
                            await _publish_event(
                                db,
                                {
                                    "event": "JOB_DISCOVERED",
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "job_id": job.id,
                                    "company": job.company,
                                    "title": job.title,
                                    "board": job.board,
                                    "score": score.total_score,
                                    "recommendation": score.recommendation,
                                },
                                application_id=application.id if application else None,
                                trace_id=application.trace_id if application else None,
                            )
                            if application is not None:
                                await prepare_application(application.id, llm_router)
                                await db.refresh(application)
                                if application.status == "ready_to_submit":
                                    await run_application(application.id, llm_router)
                            if score.total_score >= 85:
                                await _send_telegram_alert(score.total_score, job, preferences)

            task.status = "completed"
            task.jobs_found = jobs_found
            task.apps_attempted = apps_attempted
            task.completed_at = datetime.now(timezone.utc)
            task.result_summary = f"Discovered {jobs_found} new jobs and queued {apps_attempted} applications"
            await db.commit()
            await _publish_event(
                db,
                {
                    "event": "RUN_COMPLETED",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "task_id": task_id,
                    "jobs_found": jobs_found,
                    "apps_attempted": apps_attempted,
                    "apps_completed": 0,
                    "duration_seconds": int((datetime.now(timezone.utc) - started_at).total_seconds()),
                },
            )
        except Exception as exc:
            logger.exception("scan_failed", extra={"task_id": task_id})
            task.status = "failed"
            task.error_message = str(exc)
            task.completed_at = datetime.now(timezone.utc)
            await db.commit()
            await _publish_event(
                db,
                {
                    "event": "ERROR",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error_code": "SCAN_FAILED",
                    "message": str(exc),
                },
            )
        finally:
            if heartbeat_task is not None:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
            if redis is not None and lock_acquired:
                await _release_lock(redis, lock_token)
            if redis is not None:
                await redis.aclose()


async def is_scan_running() -> bool:
    redis = _redis()
    try:
        return bool(await redis.exists(SCAN_LOCK_KEY))
    finally:
        await redis.aclose()


async def acquire_scan_lock() -> str | None:
    redis = _redis()
    try:
        token = str(uuid4())
        acquired = await redis.set(SCAN_LOCK_KEY, token, nx=True, ex=SCAN_LOCK_TTL_SECONDS)
        return token if acquired else None
    finally:
        await redis.aclose()


def start_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        return
    timezone_name = os.getenv("USER_TIMEZONE", "Asia/Kolkata")
    cron_expr = os.getenv("SCHEDULE_CRON", "0 7 * * *")
    trigger = CronTrigger.from_crontab(cron_expr, timezone=timezone_name)
    _scheduler = AsyncIOScheduler(timezone=timezone_name)
    _scheduler.add_job(
        _scheduled_scan,
        trigger=trigger,
        id="morning_scan",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    _scheduler.start()
    logger.info("scanner_scheduler_started", extra={"cron": cron_expr, "timezone": timezone_name})


async def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("scanner_scheduler_stopped")
    _scheduler = None


async def _scheduled_scan() -> None:
    await run_scan(str(uuid4()), task_type="morning_scan")


async def _create_or_mark_task_running(
    db: AsyncSession,
    task_id: str,
    task_type: str,
    now: datetime,
) -> Task:
    task = await db.get(Task, task_id)
    if task is None:
        task = Task(id=task_id, task_type=task_type, status="running", scheduled_at=now, started_at=now)
        db.add(task)
    else:
        task.status = "running"
        task.started_at = now
        task.error_message = None
    await db.commit()
    await db.refresh(task)
    return task


async def _fail_task(db: AsyncSession, task: Task, message: str) -> None:
    task.status = "failed"
    task.error_message = message
    task.completed_at = datetime.now(timezone.utc)
    await db.commit()


async def _run_guard() -> dict[str, Any] | None:
    internet = await _internet_ok()
    if not internet:
        return {
            "message": "RunGuard failed: internet check to 8.8.8.8 failed",
            "event": {
                "event": "ERROR",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_code": "RUNGUARD_FAIL_INTERNET",
                "message": "Internet connectivity check failed; scan was not started.",
            },
        }
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        return {
            "message": f"RunGuard failed: database health check failed: {exc}",
            "event": {
                "event": "ERROR",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_code": "RUNGUARD_FAIL_DB",
                "message": "Database health check failed; scan was not started.",
            },
        }
    redis = _redis()
    try:
        await redis.ping()
    except Exception as exc:
        return {
            "message": f"RunGuard failed: Redis health check failed: {exc}",
            "event": {
                "event": "ERROR",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_code": "REDIS_UNAVAILABLE",
                "message": "Redis health check failed; scan was not started.",
            },
        }
    finally:
        await redis.aclose()
    return None


async def _internet_ok() -> bool:
    try:
        _reader, writer = await asyncio.wait_for(asyncio.open_connection("8.8.8.8", 53), timeout=5)
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False


async def _load_profile_and_preferences(
    db: AsyncSession,
    user_id: str | None,
) -> tuple[Resume, ResumeProfile, UserPreferences]:
    resume_query = select(Resume).where(Resume.is_active.is_(True)).order_by(Resume.created_at.desc())
    if user_id is not None:
        resume_query = resume_query.where(Resume.user_id == user_id)
    resume = await db.scalar(resume_query)
    if resume is None:
        raise RuntimeError("No active resume found for scan")
    preferences = await db.scalar(select(UserPreference).where(UserPreference.user_id == resume.user_id))
    if preferences is None:
        preferences = UserPreference(
            user_id=resume.user_id,
            target_roles=[],
            preferred_locations=[],
            work_type="any",
            experience_level="entry",
            job_types=["fulltime"],
            industry_include=[],
            industry_exclude=[],
            blacklisted_companies=[],
            dream_companies=[],
            keyword_blacklist=["10+ years", "US citizenship required", "no freshers"],
            score_threshold=70,
            max_apps_per_day=10,
            schedule_cron="0 7 * * *",
            llm_provider="gemini",
            llm_quality_mode="balanced",
            enabled_boards=["wellfound", "internshala"],
        )
        db.add(preferences)
        await db.commit()
        await db.refresh(preferences)
    return resume, ResumeProfile.model_validate(resume.profile_json), UserPreferences.model_validate(preferences)


def _selected_boards(requested: list[str] | None, preferences: UserPreferences) -> list[str]:
    boards = requested or preferences.enabled_boards or ["wellfound", "internshala"]
    normalized: list[str] = []
    for board in boards:
        key = board.strip().lower()
        if key == "linkedin":
            logger.info("linkedin_skipped_phase_3_only")
            continue
        if key not in normalized:
            normalized.append(key)
    return normalized


async def _insert_job_if_new(db: AsyncSession, board: str, detail: FullJobDetail) -> Job | None:
    content_hash = job_content_hash(detail.title, detail.company, detail.description)
    existing = await db.scalar(select(Job).where(Job.content_hash == content_hash))
    if existing is not None:
        return None
    job = Job(
        board=board,
        external_id=detail.external_id,
        title=detail.title,
        company=detail.company,
        description=detail.description,
        url=detail.url,
        location=detail.location,
        work_type=detail.work_type,
        salary_min_inr=detail.salary_min_inr,
        salary_max_inr=detail.salary_max_inr,
        experience_level=detail.experience_level,
        skills_required=detail.skills_required,
        posted_at=detail.posted_at,
        content_hash=content_hash,
        status="new",
    )
    db.add(job)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return None
    await db.refresh(job)
    return job


async def _ensure_application(
    db: AsyncSession,
    job: Job,
    resume: Resume,
    preferences: UserPreferences,
) -> Application:
    existing = await db.scalar(
        select(Application)
        .where(Application.job_id == job.id, Application.resume_id == resume.id)
        .order_by(Application.queued_at.desc())
    )
    if existing is not None:
        existing.status = "queued"
        return existing
    application = Application(
        job_id=job.id,
        resume_id=resume.id,
        is_dream_company=job.company.lower() in {company.lower() for company in preferences.dream_companies},
        status="queued",
    )
    db.add(application)
    await db.flush()
    return application


async def _publish_event(
    db: AsyncSession,
    event: dict[str, Any],
    application_id: str | None = None,
    trace_id: str | None = None,
) -> None:
    try:
        db.add(
            ApplicationEvent(
                application_id=application_id,
                trace_id=trace_id,
                event_type=str(event["event"]),
                event_data=event,
            )
        )
        await db.commit()
    except Exception as exc:
        logger.info("event_persist_failed", extra={"event": event.get("event"), "error": str(exc)})
        try:
            await db.rollback()
        except Exception:
            pass
    await websocket_manager.publish(event)


async def _send_telegram_alert(score: int, job: Job, preferences: UserPreferences) -> None:
    await send_high_score_alert(job, score)


def _redis() -> Redis:
    return Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)


async def _release_lock(redis: Redis, token: str) -> None:
    try:
        current = await redis.get(SCAN_LOCK_KEY)
        if current == token:
            await redis.delete(SCAN_LOCK_KEY)
    except Exception as exc:
        logger.info("scan_lock_release_failed", extra={"error": str(exc)})


async def _heartbeat_lock(redis: Redis, token: str) -> None:
    while True:
        await asyncio.sleep(15 * 60)
        try:
            current = await redis.get(SCAN_LOCK_KEY)
            if current != token:
                return
            await redis.expire(SCAN_LOCK_KEY, SCAN_LOCK_TTL_SECONDS)
        except Exception as exc:
            logger.info("scan_lock_heartbeat_failed", extra={"error": str(exc)})
