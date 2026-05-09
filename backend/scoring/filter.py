from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Job
from schemas.api_schemas import UserPreferences
from scrapers.base import RawJobListing, job_content_hash


@dataclass(slots=True, frozen=True)
class FilterResult:
    passed: bool
    reason: str | None = None
    matched: str | None = None


async def apply_filters(
    job: RawJobListing,
    preferences: UserPreferences,
    db: AsyncSession | None = None,
) -> FilterResult:
    company_blacklist = {company.lower() for company in preferences.blacklisted_companies}
    if job.company.lower() in company_blacklist:
        return FilterResult(passed=False, reason="BLACKLISTED_COMPANY")

    searchable = f"{job.title} {job.description or ''}".lower()
    for keyword in preferences.keyword_blacklist:
        if keyword and keyword.lower() in searchable:
            return FilterResult(passed=False, reason="BLACKLISTED_KEYWORD", matched=keyword)

    if (
        preferences.salary_min_inr
        and job.salary_max_inr
        and job.salary_max_inr < preferences.salary_min_inr
    ):
        return FilterResult(passed=False, reason="BELOW_SALARY_FLOOR")

    if job.posted_at:
        posted_at = job.posted_at
        if posted_at.tzinfo is None:
            posted_at = posted_at.replace(tzinfo=timezone.utc)
        if posted_at < datetime.now(timezone.utc) - timedelta(days=7):
            return FilterResult(passed=False, reason="TOO_OLD")

    if db is not None:
        content_hash = job.content_hash
        if content_hash is None and job.description:
            content_hash = job_content_hash(job.title, job.company, job.description)
        if content_hash:
            cutoff = datetime.now(timezone.utc) - timedelta(days=90)
            duplicate = await db.scalar(
                select(Job.id)
                .where(Job.content_hash == content_hash, Job.scraped_at >= cutoff)
                .limit(1)
            )
            if duplicate:
                return FilterResult(passed=False, reason="DUPLICATE")

    return FilterResult(passed=True)
