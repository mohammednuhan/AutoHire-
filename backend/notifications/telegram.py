from __future__ import annotations

import logging
import os
from typing import Any

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

from database.models import Job

logger = logging.getLogger("autohire.notifications.telegram")


async def send_telegram_message(text: str, reply_markup: Any | None = None) -> None:
    """Sends message to TELEGRAM_CHAT_ID from env."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return

    try:
        async with Bot(token=token) as bot:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
            )
    except TelegramError as exc:
        logger.info("telegram_message_failed", extra={"error": str(exc)})


async def send_needs_human_alert(
    application_id: str,
    company: str,
    role: str,
    field_name: str,
    reason: str,
    screenshot_available: bool,
) -> None:
    dashboard_url = f"http://localhost:3000/applications/{application_id}"
    screenshot_line = "\nScreenshot: available" if screenshot_available else ""
    message = (
        "AutoHire needs your input\n\n"
        f"Company: {company}\n"
        f"Role: {role}\n"
        f"Field: {field_name}\n"
        f"Reason: {reason}"
        f"{screenshot_line}\n\n"
        "Open dashboard to respond:\n"
        f"{dashboard_url}"
    )
    keyboard = [
        [InlineKeyboardButton("Open Dashboard", url=dashboard_url)],
        [
            InlineKeyboardButton("Answer", url=dashboard_url),
            InlineKeyboardButton("Skip", url=f"{dashboard_url}?action=skip"),
        ],
    ]
    await send_telegram_message(text=message, reply_markup=InlineKeyboardMarkup(keyboard))


async def send_morning_digest(summary: Any) -> None:
    message = (
        f"Good morning! Here is your AutoHire report for {summary.date}\n\n"
        f"Jobs scanned: {summary.jobs_scanned}\n"
        f"High-score matches: {summary.new_high_score_jobs} (score >= 85)\n"
        f"Applications submitted: {summary.apps_completed}\n"
        f"Awaiting your review: {summary.apps_needs_review}\n\n"
        "Open dashboard: http://localhost:3000"
    )
    keyboard = [[InlineKeyboardButton("Open Dashboard", url="http://localhost:3000")]]
    await send_telegram_message(text=message, reply_markup=InlineKeyboardMarkup(keyboard))


async def send_high_score_alert(job: Job, score: int) -> None:
    message = (
        f"{score}/100 match found!\n\n"
        f"Role: {job.title}\n"
        f"Company: {job.company}\n"
        f"Board: {job.board}\n\n"
        f"View job: http://localhost:3000/jobs/{job.id}"
    )
    await send_telegram_message(message)


async def send_health_alert(service_name: str, error: str) -> None:
    message = (
        "AutoHire health alert\n\n"
        f"Service: {service_name}\n"
        f"Error: {error}\n\n"
        "Open dashboard: http://localhost:3000"
    )
    await send_telegram_message(message)
