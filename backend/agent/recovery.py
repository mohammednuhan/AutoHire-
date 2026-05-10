from __future__ import annotations

from sqlalchemy import select

from browser.state_machine import publish_ws_event, send_telegram_alert, update_application_status
from database.models import Application
from database.session import AsyncSessionLocal


async def recover_interrupted_applications() -> int:
    """
    Called on every Docker startup.
    Applications left in agent_processing are from a crashed browser run.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Application).where(Application.status == "agent_processing")
        )
        applications = list(result.scalars())

    for application in applications:
        await update_application_status(
            application.id,
            "interrupted",
            failure_reason="AGENT_RESTARTED",
        )

    interrupted_count = len(applications)
    if interrupted_count > 0:
        await publish_ws_event(
            "ERROR",
            error_code="AGENT_RESTARTED",
            message=f"{interrupted_count} applications were interrupted by restart.",
        )
        await send_telegram_alert(
            f"AutoHire restarted. {interrupted_count} applications were interrupted. "
            "Open dashboard to retry."
        )

    return interrupted_count
