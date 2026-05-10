from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

logger = logging.getLogger("autohire.browser.stealth")

VIEWPORT = {"width": 1366, "height": 768}
ACCEPT_LANGUAGE = "en-IN,en;q=0.9,hi;q=0.8"

USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
]


def random_user_agent() -> str:
    return random.choice(USER_AGENTS)


def browser_context_options() -> dict[str, Any]:
    return {
        "viewport": VIEWPORT,
        "user_agent": random_user_agent(),
        "locale": "en-IN",
        "extra_http_headers": {"Accept-Language": ACCEPT_LANGUAGE},
    }


async def apply_stealth(page: Any) -> None:
    try:
        await page.set_viewport_size(VIEWPORT)
        await page.set_extra_http_headers({"Accept-Language": ACCEPT_LANGUAGE})
    except Exception as exc:
        logger.debug("browser_header_setup_failed", extra={"error": str(exc)})
    try:
        from playwright_stealth import stealth_async

        await stealth_async(page)
    except Exception as exc:
        logger.info("playwright_stealth_unavailable", extra={"error": str(exc)})


async def random_short_delay() -> float:
    delay = random.uniform(0.5, 2.0)
    await asyncio.sleep(delay)
    logger.info("browser_delay", extra={"delay_type": "short", "seconds": round(delay, 3)})
    return delay


async def random_medium_delay() -> float:
    delay = random.uniform(2.0, 5.0)
    await asyncio.sleep(delay)
    logger.info("browser_delay", extra={"delay_type": "medium", "seconds": round(delay, 3)})
    return delay


async def random_long_delay() -> float:
    delay = random.uniform(15.0, 45.0)
    await asyncio.sleep(delay)
    logger.info("browser_delay", extra={"delay_type": "long", "seconds": round(delay, 3)})
    return delay


async def random_scroll_before_click(page: Any) -> float:
    distance = random.uniform(100, 300)
    await page.mouse.wheel(0, distance)
    delay = random.uniform(0.5, 1.0)
    await asyncio.sleep(delay)
    logger.info("browser_delay", extra={"delay_type": "scroll_before_click", "seconds": round(delay, 3)})
    return delay
