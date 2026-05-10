from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy import case, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from database.models import AgentLog, Application, Job, User
from database.session import get_db
from schemas.api_schemas import MetricsResponse

router = APIRouter(tags=["metrics"])

CACHE_KEY = "autohire:metrics:v2"
CACHE_TTL_SECONDS = 60 * 60


@router.get("/api/metrics", response_model=MetricsResponse)
async def get_metrics(
    _current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    redis = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    try:
        cached = await redis.get(CACHE_KEY)
        if cached:
            return json.loads(cached)
        payload = await _calculate_metrics(db)
        await redis.set(CACHE_KEY, json.dumps(payload), ex=CACHE_TTL_SECONDS)
        return payload
    finally:
        await redis.aclose()


async def _calculate_metrics(db: AsyncSession) -> dict[str, Any]:
    confirmed = int(
        await db.scalar(select(func.count()).select_from(Application).where(Application.status == "submitted"))
        or 0
    )
    sent_from_logs = int(
        await db.scalar(
            select(func.count(distinct(AgentLog.application_id))).where(
                AgentLog.step_number == 999,
            )
        )
        or 0
    )
    sent = max(confirmed, sent_from_logs)
    confirmation_rate = round((confirmed / sent * 100), 1) if sent else 0.0

    board_rows = (
        await db.execute(
            select(
                Job.board,
                func.avg(case((AgentLog.status == "complete", 1.0), else_=0.0)),
            )
            .select_from(AgentLog)
            .join(Application, Application.id == AgentLog.application_id)
            .join(Job, Job.id == Application.job_id)
            .group_by(Job.board)
        )
    ).all()
    form_fill_success_rate = {
        board: round(float(rate or 0.0) * 100, 1) for board, rate in board_rows
    }

    confidence_avg = await db.scalar(select(func.avg(AgentLog.confidence)).where(AgentLog.confidence.is_not(None)))
    avg_seconds = await db.scalar(
        select(
            func.avg(
                func.extract("epoch", Application.completed_at - Application.started_at)
            )
        ).where(Application.started_at.is_not(None), Application.completed_at.is_not(None))
    )
    total_apps = int(await db.scalar(select(func.count()).select_from(Application)) or 0)
    needs_human = int(
        await db.scalar(
            select(func.count(distinct(AgentLog.application_id))).where(AgentLog.status == "needs_human")
        )
        or 0
    )
    human_gate_rate = round((needs_human / total_apps * 100), 1) if total_apps else 0.0

    return {
        "apps_sent_vs_confirmed": {
            "sent": sent,
            "confirmed": confirmed,
            "rate": confirmation_rate,
        },
        "form_fill_success_rate": form_fill_success_rate,
        "llm_confidence_avg": round(float(confidence_avg or 0.0), 2),
        "avg_time_per_application_seconds": int(avg_seconds or 0),
        "human_gate_trigger_rate": human_gate_rate,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
