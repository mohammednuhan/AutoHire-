from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.jobs import _job_response, _score_breakdown
from database.models import AgentLog, Application, ApplicationEvent, CoverLetter, Job, JobScore, User
from database.session import get_db
from schemas.api_schemas import (
    AgentLogEntry,
    ApplicationDetailResponse,
    ApplicationEventResponse,
    ApplicationListItem,
    CoverLetterResponse,
    JobDetailResponse,
)

router = APIRouter(tags=["applications"])


def api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": code, "message": message})


@router.get("/api/applications", response_model=list[ApplicationListItem])
async def list_applications(
    _current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ApplicationListItem]:
    rows = (
        await db.execute(
            select(Application, Job)
            .join(Job, Job.id == Application.job_id)
            .order_by(Application.queued_at.desc())
        )
    ).all()
    return [
        ApplicationListItem(
            id=application.id,
            job_id=application.job_id,
            resume_id=application.resume_id,
            trace_id=application.trace_id,
            title=job.title,
            company=job.company,
            board=job.board,
            is_dream_company=application.is_dream_company,
            status=application.status,
            failure_reason=application.failure_reason,
            queued_at=application.queued_at,
            started_at=application.started_at,
            completed_at=application.completed_at,
            submitted_at=application.submitted_at,
        )
        for application, job in rows
    ]


@router.get("/api/applications/{application_id}", response_model=ApplicationDetailResponse)
async def get_application(
    application_id: str,
    _current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApplicationDetailResponse:
    row = await db.execute(
        select(Application, Job)
        .join(Job, Job.id == Application.job_id)
        .where(Application.id == application_id)
    )
    result = row.first()
    if result is None:
        raise api_error(404, "NOT_FOUND", "Application not found")
    application, job = result
    score = await db.scalar(
        select(JobScore)
        .where(JobScore.job_id == job.id, JobScore.resume_id == application.resume_id)
        .order_by(JobScore.scored_at.desc())
    )
    cover_letter = await db.scalar(select(CoverLetter).where(CoverLetter.application_id == application.id))
    logs = (
        await db.execute(
            select(AgentLog).where(AgentLog.application_id == application.id).order_by(AgentLog.created_at.asc())
        )
    ).scalars().all()
    events = (
        await db.execute(
            select(ApplicationEvent)
            .where(ApplicationEvent.application_id == application.id)
            .order_by(ApplicationEvent.created_at.asc())
        )
    ).scalars().all()
    job_payload = _job_response(job, score).model_dump()
    return ApplicationDetailResponse(
        id=application.id,
        job_id=application.job_id,
        resume_id=application.resume_id,
        trace_id=application.trace_id,
        title=job.title,
        company=job.company,
        board=job.board,
        is_dream_company=application.is_dream_company,
        status=application.status,
        failure_reason=application.failure_reason,
        queued_at=application.queued_at,
        started_at=application.started_at,
        completed_at=application.completed_at,
        submitted_at=application.submitted_at,
        notes=application.notes,
        tailored_resume_pdf_path=application.tailored_resume_pdf_path,
        tailored_resume_docx_path=application.tailored_resume_docx_path,
        job=JobDetailResponse(
            **job_payload,
            description=job.description,
            content_hash=job.content_hash,
            score_breakdown=_score_breakdown(score),
        ),
        cover_letter=CoverLetterResponse.model_validate(cover_letter) if cover_letter else None,
        agent_log=[AgentLogEntry.model_validate(log) for log in logs],
        events=[ApplicationEventResponse.model_validate(event) for event in events],
    )


@router.put("/api/applications/{application_id}/status", response_model=dict[str, str])
async def update_status(
    application_id: str,
    payload: dict[str, str],
    _current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    status = payload.get("status")
    if not status:
        raise api_error(400, "INVALID_STATUS", "Status is required")
    result = await db.execute(update(Application).where(Application.id == application_id).values(status=status))
    if result.rowcount == 0:
        raise api_error(404, "NOT_FOUND", "Application not found")
    await db.commit()
    return {"application_id": application_id, "status": status}


@router.get("/api/applications/{application_id}/resume.pdf")
async def get_resume_pdf(
    application_id: str,
    _current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FileResponse:
    application = await db.get(Application, application_id)
    if application is None or not application.tailored_resume_pdf_path:
        raise api_error(404, "NOT_FOUND", "Tailored PDF not found")
    return FileResponse(application.tailored_resume_pdf_path, media_type="application/pdf")


@router.get("/api/applications/{application_id}/resume.docx")
async def get_resume_docx(
    application_id: str,
    _current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FileResponse:
    application = await db.get(Application, application_id)
    if application is None or not application.tailored_resume_docx_path:
        raise api_error(404, "NOT_FOUND", "Tailored DOCX not found")
    return FileResponse(
        application.tailored_resume_docx_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
