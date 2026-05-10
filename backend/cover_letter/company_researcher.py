from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from cover_letter.models import CompanyResearch
from cover_letter.text_utils import json_payload
from database.models import CompanyCache
from database.session import AsyncSessionLocal
from llm.client import LLMFailure, LLMRouter
from llm.prompts import COMPANY_RESEARCH_PROMPT, COMPANY_RESEARCH_SYSTEM
from resume.safety import ContentSafetyError, sanitize_user_content

logger = logging.getLogger("autohire.cover_letter.company_researcher")

CACHE_TTL_DAYS = 7


class CompanyResearchError(Exception):
    pass


async def research_company(company_name: str, llm_router: LLMRouter) -> CompanyResearch:
    company_name_key = company_name.lower().strip()
    if not company_name_key:
        return CompanyResearch(known=False)

    cached = await _get_cached_research(company_name_key)
    if cached is not None:
        return cached

    try:
        safe_company_name = sanitize_user_content(company_name)[:255]
    except ContentSafetyError as exc:
        raise CompanyResearchError(f"Unsafe company name rejected: {exc}") from exc

    prompt = COMPANY_RESEARCH_PROMPT.format(company_name=safe_company_name)
    try:
        response = await llm_router.call_with_retry(
            task_type="reason",
            prompt=prompt,
            system=COMPANY_RESEARCH_SYSTEM,
            response_format="json",
            max_retries=3,
            trace_id=str(uuid4()),
        )
        research = CompanyResearch.model_validate(json_payload(response))
    except (LLMFailure, ValidationError, ValueError) as exc:
        logger.warning("company_research_failed", extra={"company": company_name_key, "error": str(exc)})
        research = CompanyResearch(known=False)

    if not research.known:
        research = CompanyResearch(known=False)

    await _save_cached_research(company_name_key, research)
    return research


async def _get_cached_research(company_name_key: str) -> CompanyResearch | None:
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        cached = await db.scalar(
            select(CompanyCache).where(
                CompanyCache.company_name_key == company_name_key,
                CompanyCache.expires_at > now,
            )
        )
        if cached is None:
            return None
        if not bool(getattr(cached, "known", True)):
            return CompanyResearch(known=False)
        return CompanyResearch(
            known=True,
            industry=getattr(cached, "industry", None),
            what_they_do=getattr(cached, "what_they_do", None) or cached.mission,
            culture_signals=cached.culture_signals or getattr(cached, "values_text", None),
            why_interesting=getattr(cached, "why_interesting", None) or cached.recent_news,
        )


async def _save_cached_research(company_name_key: str, research: CompanyResearch) -> None:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=CACHE_TTL_DAYS)
    async with AsyncSessionLocal() as db:
        cached = await db.scalar(select(CompanyCache).where(CompanyCache.company_name_key == company_name_key))
        if cached is None:
            cached = CompanyCache(company_name_key=company_name_key)
            db.add(cached)

        cached.known = research.known
        cached.industry = research.industry
        cached.what_they_do = research.what_they_do
        cached.mission = research.what_they_do
        cached.culture_signals = research.culture_signals
        cached.values_text = research.culture_signals
        cached.why_interesting = research.why_interesting
        cached.recent_news = research.why_interesting
        cached.cached_at = now
        cached.expires_at = expires_at

        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            logger.info("company_research_cache_race", extra={"company": company_name_key})
