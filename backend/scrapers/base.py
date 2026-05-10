from __future__ import annotations

import asyncio
import hashlib
import random
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from html import unescape
from typing import Any, ClassVar
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


class DailyScrapeLimitExceeded(Exception):
    pass


class ScraperStopped(Exception):
    pass


REALISTIC_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


COMMON_HEADERS = {
    "User-Agent": REALISTIC_USER_AGENT,
    "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
}


@dataclass(slots=True, kw_only=True)
class RawJobListing:
    external_id: str
    title: str
    company: str
    url: str
    location: str | None = None
    work_type: str | None = None
    posted_at: datetime | None = None
    salary_range: str | None = None
    salary_min_inr: int | None = None
    salary_max_inr: int | None = None
    description: str | None = None
    skills_required: list[str] = field(default_factory=list)
    experience_level: str | None = None
    content_hash: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, kw_only=True)
class FullJobDetail(RawJobListing):
    description: str = ""
    skills_required: list[str] = field(default_factory=list)
    experience_level: str | None = None


class BoardScraper(ABC):
    board_name: str
    max_daily_scrapes: int
    min_delay_seconds: int
    max_delay_seconds: int
    _daily_scrape_counts: ClassVar[dict[tuple[str, date], int]] = {}

    def __init__(self) -> None:
        self._scrape_count = 0
        self._scrape_day = date.today()

    @abstractmethod
    async def scrape_listings(
        self,
        target_roles: list[str],
        location: str,
        max_results: int = 50,
    ) -> list[RawJobListing]:
        """Scrape job listing summaries. Must respect rate limits."""

    @abstractmethod
    async def extract_job_detail(self, listing: RawJobListing) -> FullJobDetail:
        """Fetch full job description for a single listing."""

    async def random_delay(self) -> None:
        """Enforced delay between requests. Always call between page loads."""
        delay = random.uniform(self.min_delay_seconds, self.max_delay_seconds)
        await asyncio.sleep(delay)

    async def before_page_load(self) -> None:
        today = date.today()
        if today != self._scrape_day:
            self._scrape_day = today
            self._scrape_count = 0
        key = (self.board_name, today)
        for stale_key in list(self._daily_scrape_counts):
            if stale_key[0] == self.board_name and stale_key[1] != today:
                del self._daily_scrape_counts[stale_key]
        daily_count = self._daily_scrape_counts.get(key, 0)
        if daily_count >= self.max_daily_scrapes:
            raise DailyScrapeLimitExceeded(
                f"{self.board_name} daily scrape limit reached: {self.max_daily_scrapes}"
            )
        if daily_count > 0 and self.max_delay_seconds > 0:
            await self.random_delay()
        self._daily_scrape_counts[key] = daily_count + 1
        self._scrape_count = daily_count + 1


def normalize_space(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", unescape(value)).strip()


def html_to_plain_text(html: str | None) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return normalize_space(soup.get_text(" "))


def absolute_url(base_url: str, href: str | None) -> str:
    if not href:
        return base_url
    return urljoin(base_url, href)


def external_id_from_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.strip("/") or parsed.netloc
    return path[-500:]


def infer_work_type(text: str | None) -> str | None:
    normalized = (text or "").lower()
    if "work from home" in normalized or "remote" in normalized:
        return "remote"
    if "hybrid" in normalized:
        return "hybrid"
    if normalized:
        return "onsite"
    return None


def parse_posted_at(value: str | None) -> datetime | None:
    if not value:
        return None
    text = normalize_space(value).lower()
    now = datetime.now(timezone.utc)
    if text in {"today", "just now"}:
        return now
    if text == "yesterday":
        return now - timedelta(days=1)
    match = re.search(r"(\d+)\s*(minute|hour|day|week|month)s?\s+ago", text)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        if unit == "minute":
            return now - timedelta(minutes=amount)
        if unit == "hour":
            return now - timedelta(hours=amount)
        if unit == "day":
            return now - timedelta(days=amount)
        if unit == "week":
            return now - timedelta(weeks=amount)
        if unit == "month":
            return now - timedelta(days=30 * amount)
    try:
        parsed = datetime.fromisoformat(text.replace("z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_salary_range_inr(value: str | None) -> tuple[int | None, int | None]:
    if not value:
        return None, None
    text = normalize_space(value).lower().replace(",", "")
    if not any(token in text for token in ("rs", "inr", "lpa", "lakh", "stipend", "salary", "ctc")):
        return None, None

    numbers = [float(match) for match in re.findall(r"(\d+(?:\.\d+)?)", text)]
    if not numbers:
        return None, None

    multiplier = 1
    if "lpa" in text or "lakh" in text or "lac" in text:
        multiplier = 100000
    elif "k" in text:
        multiplier = 1000

    values = [int(number * multiplier) for number in numbers]
    if "/month" in text or "per month" in text or "month" in text:
        values = [value * 12 for value in values]
    if len(values) == 1:
        return None, values[0]
    return min(values), max(values)


KNOWN_SKILLS = [
    "python",
    "java",
    "javascript",
    "typescript",
    "react",
    "next.js",
    "node.js",
    "django",
    "fastapi",
    "flask",
    "sql",
    "postgresql",
    "mysql",
    "mongodb",
    "redis",
    "aws",
    "gcp",
    "azure",
    "docker",
    "kubernetes",
    "linux",
    "git",
    "machine learning",
    "data science",
    "nlp",
    "llm",
    "tensorflow",
    "pytorch",
    "html",
    "css",
    "tailwind",
    "figma",
]


def extract_skills_from_text(text: str | None) -> list[str]:
    normalized = f" {normalize_space(text).lower()} "
    skills: list[str] = []
    for skill in KNOWN_SKILLS:
        pattern = rf"(?<![a-z0-9.+#]){re.escape(skill)}(?![a-z0-9.+#])"
        if re.search(pattern, normalized):
            skills.append(skill)
    return skills


def job_content_hash(title: str, company: str, description: str | None) -> str:
    basis = f"{title.lower()}{company.lower()}{(description or '')[:500]}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()
