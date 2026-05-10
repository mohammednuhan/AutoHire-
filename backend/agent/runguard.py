from __future__ import annotations

import os

import httpx
from redis.asyncio import Redis
from sqlalchemy import text

from browser.models import RunGuardResult
from browser.state_machine import publish_ws_event
from database.session import engine
from notifications.telegram import send_health_alert


async def run_preflight_checks() -> RunGuardResult:
    """Called before every scheduled or on-demand browser agent run."""
    checks: dict[str, str] = {}

    try:
        async with httpx.AsyncClient(timeout=5, verify=False) as client:
            await client.get("https://8.8.8.8")
        checks["internet"] = "ok"
    except Exception:
        checks["internet"] = "failed"

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception:
        checks["db"] = "failed"

    redis = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "failed"
    finally:
        await redis.aclose()

    all_passed = all(value == "ok" for value in checks.values())
    if not all_passed:
        failed = [key for key, value in checks.items() if value != "ok"]
        error_code = f"RUNGUARD_FAIL_{'_AND_'.join(failed).upper()}"
        await publish_ws_event(
            "ERROR",
            error_code=error_code,
            message=f"Pre-run check failed: {', '.join(failed)}",
        )
        await send_health_alert("RunGuard", f"Pre-run check failed: {', '.join(failed)}")

    return RunGuardResult(passed=all_passed, checks=checks)
