from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select

from browser.models import Action
from browser.state_machine import publish_ws_event
from database.models import FormTemplateCache
from database.session import AsyncSessionLocal

logger = logging.getLogger("autohire.browser.template_cache")


def normalize_url_pattern(url: str) -> str:
    parsed = urlparse(url)
    path = re.sub(r"/[0-9a-fA-F-]{8,}", "/*", parsed.path)
    path = re.sub(r"/\d+", "/*", path)
    path = re.sub(r"/[^/]*job[^/]*-\d+[^/]*", "/*", path, flags=re.IGNORECASE)
    return f"{parsed.scheme}://{parsed.netloc.lower().lstrip('www.')}{path}"


def structure_hash(field_map: dict[str, Any]) -> str:
    return hashlib.sha256(repr(sorted(field_map.items())).encode("utf-8")).hexdigest()


async def get_cached_field_map(board: str, url: str) -> dict[str, Any] | None:
    pattern = normalize_url_pattern(url)
    async with AsyncSessionLocal() as db:
        cache = await db.scalar(
            select(FormTemplateCache).where(
                FormTemplateCache.board == board,
                FormTemplateCache.page_url_pattern == pattern,
            )
        )
        if cache is None:
            return None
        cache.hit_count = (cache.hit_count or 0) + 1
        cache.last_used_at = datetime.now(timezone.utc)
        await db.commit()
        await publish_ws_event(
            "BROWSER_ACTION",
            step=0,
            action="template_cache_hit",
            field=pattern,
            confidence=1.0,
        )
        logger.info("template_cache_hit", extra={"board": board, "pattern": pattern})
        return cache.field_map


async def save_field_map(board: str, url: str, actions: list[Action]) -> None:
    pattern = normalize_url_pattern(url)
    field_map = {
        "actions": [
            {
                "action": action.action,
                "field_description": action.field_description,
                "selector": action.selector,
                "expected_state": action.expected_state,
            }
            for action in actions
            if action.field_description and action.action in {"fill", "click", "select", "upload", "checkbox"}
        ]
    }
    digest = structure_hash(field_map)
    async with AsyncSessionLocal() as db:
        cache = await db.scalar(
            select(FormTemplateCache).where(
                FormTemplateCache.board == board,
                FormTemplateCache.page_url_pattern == pattern,
            )
        )
        if cache is None:
            db.add(
                FormTemplateCache(
                    board=board,
                    page_url_pattern=pattern,
                    page_structure_hash=digest,
                    field_map=field_map,
                )
            )
        elif cache.page_structure_hash != digest:
            cache.page_structure_hash = digest
            cache.field_map = field_map
            cache.cached_at = datetime.now(timezone.utc)
        await db.commit()


def apply_cached_selectors(actions: list[Action], field_map: dict[str, Any] | None) -> list[Action]:
    if not field_map:
        return actions
    selectors = {
        (item.get("action"), item.get("field_description")): item.get("selector")
        for item in field_map.get("actions", [])
        if item.get("selector")
    }
    patched: list[Action] = []
    for action in actions:
        selector = selectors.get((action.action, action.field_description))
        if selector and not action.selector:
            data = action.model_dump()
            data["selector"] = selector
            action = Action.model_validate(data)
        patched.append(action)
    return patched
