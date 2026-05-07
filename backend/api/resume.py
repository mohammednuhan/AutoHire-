from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from database.models import ApplicationEvent, Resume, User, UserPreference
from database.session import get_db
from llm.client import LLMRouter
from resume.extractor import ExtractionError, detect_file_type, extract_text
from resume.parser import ParseError, parse_resume
from schemas.api_schemas import ResumeProfile, UserPreferences
from storage import FileTooLargeError, new_resume_id, save_uploaded_file
from websocket import websocket_manager

router = APIRouter(tags=["resume"])


def api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": code, "message": message})


def _preference_dict(preferences: UserPreference) -> dict[str, Any]:
    return {
        "target_roles": preferences.target_roles or [],
        "preferred_locations": preferences.preferred_locations or [],
        "work_type": preferences.work_type,
        "salary_min_inr": preferences.salary_min_inr,
        "salary_max_inr": preferences.salary_max_inr,
        "experience_level": preferences.experience_level,
        "job_types": preferences.job_types or ["fulltime"],
        "industry_include": preferences.industry_include or [],
        "industry_exclude": preferences.industry_exclude or [],
        "blacklisted_companies": preferences.blacklisted_companies or [],
        "dream_companies": preferences.dream_companies or [],
        "keyword_blacklist": preferences.keyword_blacklist or [],
        "score_threshold": preferences.score_threshold,
        "max_apps_per_day": preferences.max_apps_per_day,
        "schedule_cron": preferences.schedule_cron,
        "telegram_chat_id": preferences.telegram_chat_id,
        "llm_provider": preferences.llm_provider,
        "llm_quality_mode": preferences.llm_quality_mode,
        "enabled_boards": preferences.enabled_boards or [],
    }


async def _get_active_resume(db: AsyncSession, user_id: str) -> Resume | None:
    return await db.scalar(
        select(Resume)
        .where(Resume.user_id == user_id, Resume.is_active.is_(True))
        .order_by(Resume.created_at.desc())
    )


async def _get_or_create_preferences(db: AsyncSession, user_id: str) -> UserPreference:
    preferences = await db.scalar(select(UserPreference).where(UserPreference.user_id == user_id))
    if preferences is None:
        preferences = UserPreference(
            user_id=user_id,
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
        await db.flush()
    return preferences


@router.post("/api/resume/upload")
async def upload_resume(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: Annotated[UploadFile, File()],
) -> dict[str, Any]:
    resume_id = new_resume_id()
    try:
        saved_path = await save_uploaded_file(file, resume_id)
    except FileTooLargeError:
        raise api_error(400, "FILE_TOO_LARGE", "Maximum file size is 10MB") from None

    try:
        file_type = detect_file_type(saved_path)
    except ExtractionError:
        raise api_error(400, "INVALID_FILE_TYPE", "Only PDF and DOCX files are accepted") from None
    if file_type not in {"pdf", "docx"}:
        raise api_error(400, "INVALID_FILE_TYPE", "Only PDF and DOCX files are accepted")
    normalized_path = str(Path(saved_path).with_name(f"original.{file_type}"))
    if normalized_path != saved_path:
        Path(saved_path).replace(normalized_path)
        saved_path = normalized_path

    try:
        raw_text = extract_text(saved_path)
    except ExtractionError:
        raise api_error(
            422,
            "PARSE_FAILED",
            "Could not extract readable text. Try a text-based PDF - scanned image PDFs are not supported.",
        ) from None

    llm_event = {
        "event": "LLM_CALL",
        "purpose": "resume_extraction",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    db.add(
        ApplicationEvent(
            event_type="LLM_CALL",
            event_data=llm_event,
        )
    )
    await websocket_manager.publish(llm_event)

    try:
        profile = await parse_resume(raw_text, LLMRouter())
    except ParseError as exc:
        if exc.missing_fields:
            raise api_error(
                422,
                "EXTRACTION_INCOMPLETE",
                f"Resume parsed but missing required fields: {exc.missing_fields}. Please review and edit your profile.",
            ) from exc
        raise api_error(
            422,
            "PARSE_FAILED",
            "Could not extract readable text. Try a text-based PDF - scanned image PDFs are not supported.",
        ) from exc

    await db.execute(
        Resume.__table__.update()
        .where(Resume.user_id == current_user.id)
        .values(is_active=False)
    )
    resume = Resume(
        id=resume_id,
        user_id=current_user.id,
        original_filename=file.filename or "resume",
        original_file_path=saved_path,
        raw_text=raw_text,
        profile_json=profile.model_dump(),
        is_active=True,
        parsed_at=datetime.now(timezone.utc),
    )
    db.add(resume)
    await _get_or_create_preferences(db, current_user.id)
    await db.commit()

    return {"resume_id": resume.id, "status": "parsed", "profile": profile.model_dump()}


@router.get("/api/profile")
async def get_profile(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    resume = await _get_active_resume(db, current_user.id)
    if resume is None:
        raise api_error(404, "NOT_FOUND", "No resume has been uploaded yet")
    preferences = await _get_or_create_preferences(db, current_user.id)
    await db.commit()
    return {
        "resume_id": resume.id,
        "profile": resume.profile_json,
        "preferences": _preference_dict(preferences),
    }


@router.put("/api/profile")
async def update_profile(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    updates: Annotated[dict[str, Any], Body()],
) -> dict[str, Any]:
    resume = await _get_active_resume(db, current_user.id)
    if resume is None:
        raise api_error(404, "NOT_FOUND", "No resume has been uploaded yet")
    preferences = await _get_or_create_preferences(db, current_user.id)

    profile_data = dict(resume.profile_json)
    preference_data = _preference_dict(preferences)
    updated_fields: list[str] = []

    for key, value in updates.items():
        storage_key = "target_roles" if key == "preferred_roles" else key
        if storage_key in preference_data:
            preference_data[storage_key] = value
            setattr(preferences, storage_key, value)
            updated_fields.append(key)
        elif storage_key in profile_data:
            profile_data[storage_key] = value
            updated_fields.append(key)

    try:
        ResumeProfile.model_validate(profile_data)
        UserPreferences.model_validate(preference_data)
    except ValidationError as exc:
        raise api_error(422, "EXTRACTION_INCOMPLETE", str(exc)) from exc

    resume.profile_json = profile_data
    await db.commit()
    return {"status": "updated", "updated_fields": updated_fields}


@router.get("/api/profile/completeness")
async def profile_completeness(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    resume = await _get_active_resume(db, current_user.id)
    if resume is None:
        raise api_error(404, "NOT_FOUND", "No resume has been uploaded yet")
    preferences = await _get_or_create_preferences(db, current_user.id)
    profile = ResumeProfile.model_validate(resume.profile_json)
    prefs = UserPreferences.model_validate(_preference_dict(preferences))

    score = 0
    missing: list[str] = []

    checks = [
        ("full_name", bool(profile.full_name), 15),
        ("email", bool(profile.email), 15),
        ("experience", len(profile.experience) >= 1, 20),
        ("projects.tech_stack", any(project.tech_stack for project in profile.projects), 15),
        ("skills.languages", bool(profile.skills.languages), 15),
        ("education.graduation_year", any(item.graduation_year for item in profile.education), 10),
        ("target_roles", bool(prefs.target_roles), 10),
    ]
    for field, passed, points in checks:
        if passed:
            score += points
        else:
            missing.append(field)

    return {"score": score, "missing_fields": missing}
