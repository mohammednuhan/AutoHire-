from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import quote_plus

from browser.profile_manager import BrowserProfileManager
from browser.security import DomainAllowlist
from browser.stealth import apply_stealth, browser_context_options
from scrapers.base import (
    BoardScraper,
    FullJobDetail,
    RawJobListing,
    extract_skills_from_text,
    html_to_plain_text,
    infer_work_type,
    normalize_space,
    parse_posted_at,
    parse_salary_range_inr,
)

logger = logging.getLogger("autohire.scrapers.foundit")


class FounditScraper(BoardScraper):
    board_name = "foundit"
    max_daily_scrapes = 15
    min_delay_seconds = 45
    max_delay_seconds = 90
    base_url = "https://www.foundit.in"

    async def scrape_listings(
        self,
        target_roles: list[str],
        location: str,
        max_results: int = 50,
    ) -> list[RawJobListing]:
        listings: list[RawJobListing] = []
        seen: set[str] = set()
        async with _persistent_context(self.board_name) as context:
            page = await context.new_page()
            await apply_stealth(page)
            await DomainAllowlist().install_on_page(page)
            for role in target_roles:
                if len(listings) >= min(max_results, 15):
                    break
                await self.before_page_load()
                url = self._search_url(role, location)
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(2000)
                for listing in await _listings_from_dom(page):
                    if listing.external_id in seen:
                        continue
                    seen.add(listing.external_id)
                    listings.append(listing)
                    if len(listings) >= min(max_results, 15):
                        break
        return listings[: min(max_results, 15)]

    async def extract_job_detail(self, listing: RawJobListing) -> FullJobDetail:
        async with _persistent_context(self.board_name) as context:
            page = await context.new_page()
            await apply_stealth(page)
            await DomainAllowlist().install_on_page(page)
            await self.before_page_load()
            await page.goto(listing.url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(1500)
            html = await page.content()
        description = html_to_plain_text(html) or listing.description or listing.title
        salary_min, salary_max = parse_salary_range_inr(listing.salary_range or description)
        return FullJobDetail(
            external_id=listing.external_id,
            title=listing.title,
            company=listing.company,
            url=listing.url,
            location=listing.location,
            work_type=listing.work_type or infer_work_type(description),
            posted_at=listing.posted_at,
            salary_range=listing.salary_range,
            salary_min_inr=listing.salary_min_inr or salary_min,
            salary_max_inr=listing.salary_max_inr or salary_max,
            description=description,
            skills_required=sorted(set(listing.skills_required + extract_skills_from_text(description))),
            experience_level=listing.experience_level,
            metadata=listing.metadata,
        )

    def _search_url(self, role: str, location: str) -> str:
        return (
            f"{self.base_url}/srp/results?"
            f"searchId={quote_plus(role)}&locationId={quote_plus(location)}"
        )


class _persistent_context:
    def __init__(self, board: str) -> None:
        self.board = board
        self.playwright: Any | None = None
        self.context: Any | None = None

    async def __aenter__(self) -> Any:
        from playwright.async_api import async_playwright

        manager = BrowserProfileManager()
        profile_options = await manager.load_profile(self.board)
        self.playwright = await async_playwright().start()
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=profile_options["user_data_dir"],
            headless=True,
            **browser_context_options(),
        )
        return self.context

    async def __aexit__(self, *_exc: object) -> None:
        if self.context is not None:
            await self.context.close()
        if self.playwright is not None:
            await self.playwright.stop()


async def _listings_from_dom(page: Any) -> list[RawJobListing]:
    cards = await page.locator("article, .cardContainer, .srpResultCard, [data-testid*='job']").all()
    listings: list[RawJobListing] = []
    for card in cards[:15]:
        try:
            anchor = card.locator("a[href*='foundit.in']").first()
            url = await anchor.get_attribute("href")
            title = normalize_space(await anchor.inner_text())
            text = normalize_space(await card.inner_text())
        except Exception:
            continue
        if not url or not title:
            continue
        company = _company_from_text(text, title)
        salary_min, salary_max = parse_salary_range_inr(text)
        listings.append(
            RawJobListing(
                external_id=url.rstrip("/").split("/")[-1][:500],
                title=title[:500],
                company=company[:255] or "Unknown",
                url=url,
                location=_known_location(text),
                work_type=infer_work_type(text),
                posted_at=parse_posted_at(text),
                salary_range=text if salary_max else None,
                salary_min_inr=salary_min,
                salary_max_inr=salary_max,
                description=text[:1000],
                skills_required=extract_skills_from_text(text),
                experience_level=_experience_from_text(text),
            )
        )
    return listings


def _company_from_text(text: str, title: str) -> str:
    parts = [part.strip(" -|") for part in text.splitlines() if part.strip()]
    for index, part in enumerate(parts):
        if title in part and index + 1 < len(parts):
            return parts[index + 1]
    return parts[1] if len(parts) > 1 else ""


def _known_location(text: str) -> str | None:
    lowered = text.lower()
    for city in ["bengaluru", "bangalore", "mumbai", "pune", "delhi", "gurgaon", "hyderabad", "chennai", "noida"]:
        if city in lowered:
            return city.title()
    return None


def _experience_from_text(text: str) -> str | None:
    match = re.search(r"\d+\s*-\s*\d+\s*Yrs|\d+\s*Yrs", text, flags=re.IGNORECASE)
    return match.group(0) if match else None
