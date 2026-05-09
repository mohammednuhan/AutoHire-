from __future__ import annotations

import asyncio
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agent.scanner import is_scan_running, run_scan
from api.auth import get_current_user
from database.models import Application, Job, JobScore, Resume, Task, User, UserPreference
from database.session import get_db
from schemas.api_schemas import (
    AgentRunRequest,
    AgentRunResponse,
    JobDetailResponse,
    JobResponse,
    JobsPageResponse,
    ScoreBreakdown,
    TaskResponse,
)

router = APIRouter(tags=["jobs"])


def api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": code, "message": message})


async def _active_resume(db: AsyncSession, user_id: str) -> Resume | None:
    return await db.scalar(
        select(Resume)
        .where(Resume.user_id == user_id, Resume.is_active.is_(True))
        .order_by(Resume.created_at.desc())
    )


async def _preferences(db: AsyncSession, user_id: str) -> UserPreference | None:
    return await db.scalar(select(UserPreference).where(UserPreference.user_id == user_id))


def _job_response(job: Job, score: JobScore | None) -> JobResponse:
    return JobResponse(
        id=job.id,
        board=job.board,
        external_id=job.external_id,
        title=job.title,
        company=job.company,
        url=job.url,
        location=job.location,
        work_type=job.work_type,
        salary_min_inr=job.salary_min_inr,
        salary_max_inr=job.salary_max_inr,
        experience_level=job.experience_level,
        skills_required=job.skills_required or [],
        posted_at=job.posted_at,
        scraped_at=job.scraped_at,
        status=job.status,
        total_score=score.total_score if score else None,
        recommendation=score.recommendation if score else None,
    )


def _score_breakdown(score: JobScore | None) -> ScoreBreakdown | None:
    if score is None:
        return None
    return ScoreBreakdown(
        total_score=score.total_score,
        technical_match=score.technical_match,
        experience_match=score.experience_match,
        domain_match=score.domain_match,
        location_match=score.location_match,
        growth_potential=score.growth_potential,
        missing_skills=score.missing_skills or [],
        matching_skills=score.matching_skills or [],
        score_explanation=score.score_explanation,
        recommendation=score.recommendation,
        scored_at=score.scored_at,
    )


@router.get("/api/jobs", response_model=JobsPageResponse)
async def list_jobs(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
    score_min: Annotated[int | None, Query(ge=0, le=100)] = None,
    score_max: Annotated[int | None, Query(ge=0, le=100)] = None,
    board: str | None = None,
    status: str | None = None,
    work_type: str | None = None,
    sort: Literal["score_desc", "date_desc", "date_asc"] = "score_desc",
) -> JobsPageResponse:
    resume = await _active_resume(db, current_user.id)
    score_join = JobScore.job_id == Job.id
    if resume is not None:
        score_join = and_(score_join, JobScore.resume_id == resume.id)

    conditions = []
    if board:
        conditions.append(Job.board == board)
    if status:
        conditions.append(Job.status == status)
    if work_type:
        conditions.append(Job.work_type == work_type)
    if score_min is not None:
        conditions.append(JobScore.total_score >= score_min)
    if score_max is not None:
        conditions.append(JobScore.total_score <= score_max)

    total_query = select(func.count()).select_from(Job).outerjoin(JobScore, score_join)
    list_query = select(Job, JobScore).outerjoin(JobScore, score_join)
    if conditions:
        total_query = total_query.where(and_(*conditions))
        list_query = list_query.where(and_(*conditions))

    if sort == "date_asc":
        list_query = list_query.order_by(Job.scraped_at.asc())
    elif sort == "date_desc":
        list_query = list_query.order_by(Job.scraped_at.desc())
    else:
        list_query = list_query.order_by(JobScore.total_score.desc().nullslast(), Job.scraped_at.desc())

    total = await db.scalar(total_query)
    rows = (
        await db.execute(list_query.offset((page - 1) * per_page).limit(per_page))
    ).all()
    return JobsPageResponse(
        page=page,
        per_page=per_page,
        total=int(total or 0),
        items=[_job_response(job, score) for job, score in rows],
    )


@router.get("/api/jobs/{job_id}", response_model=JobDetailResponse)
async def get_job(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JobDetailResponse:
    job = await db.get(Job, job_id)
    if job is None:
        raise api_error(404, "NOT_FOUND", "Job not found")
    resume = await _active_resume(db, current_user.id)
    score_query = select(JobScore).where(JobScore.job_id == job.id).order_by(JobScore.scored_at.desc())
    if resume is not None:
        score_query = score_query.where(JobScore.resume_id == resume.id)
    score = await db.scalar(score_query)
    base = _job_response(job, score).model_dump()
    return JobDetailResponse(
        **base,
        description=job.description,
        content_hash=job.content_hash,
        score_breakdown=_score_breakdown(score),
    )


@router.post("/api/jobs/{job_id}/queue", response_model=dict[str, str])
async def queue_job(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    resume = await _active_resume(db, current_user.id)
    if resume is None:
        raise api_error(404, "NOT_FOUND", "No active resume found")
    job = await db.get(Job, job_id)
    if job is None:
        raise api_error(404, "NOT_FOUND", "Job not found")
    preferences = await _preferences(db, current_user.id)
    dream_companies = {company.lower() for company in (preferences.dream_companies if preferences else [])}
    application = await db.scalar(
        select(Application)
        .where(Application.job_id == job.id, Application.resume_id == resume.id)
        .order_by(Application.queued_at.desc())
    )
    if application is None:
        application = Application(
            job_id=job.id,
            resume_id=resume.id,
            is_dream_company=job.company.lower() in dream_companies,
            status="queued",
        )
        db.add(application)
    else:
        application.status = "queued"
        application.is_dream_company = job.company.lower() in dream_companies
    job.status = "queued"
    await db.flush()
    await db.commit()
    return {"job_id": job.id, "application_id": application.id, "status": "queued"}


@router.post("/api/jobs/{job_id}/skip", response_model=dict[str, str])
async def skip_job(
    job_id: str,
    _current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    result = await db.execute(update(Job).where(Job.id == job_id).values(status="skipped"))
    if result.rowcount == 0:
        raise api_error(404, "NOT_FOUND", "Job not found")
    await db.commit()
    return {"job_id": job_id, "status": "skipped"}


@router.post("/api/agent/run", response_model=AgentRunResponse)
async def run_agent_scan(
    current_user: Annotated[User, Depends(get_current_user)],
    payload: AgentRunRequest | None = None,
) -> AgentRunResponse:
    try:
        if await is_scan_running():
            raise api_error(409, "SCAN_ALREADY_RUNNING", "A scan is already running")
    except HTTPException:
        raise
    except Exception as exc:
        raise api_error(503, "REDIS_UNAVAILABLE", f"Could not check scan lock: {exc}") from exc

    task_id = uuid4()
    asyncio.create_task(
        run_scan(
            str(task_id),
            boards=payload.boards if payload else None,
            user_id=current_user.id,
            task_type="on_demand_scan",
        )
    )
    return AgentRunResponse(task_id=task_id, status="started")


@router.get("/api/tasks", response_model=list[TaskResponse])
async def list_tasks(
    _current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[TaskResponse]:
    tasks = (
        await db.execute(select(Task).order_by(Task.scheduled_at.desc()).limit(10))
    ).scalars().all()
    return [TaskResponse.model_validate(task) for task in tasks]
