from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup, Tag

from scrapers.base import (
    COMMON_HEADERS,
    BoardScraper,
    DailyScrapeLimitExceeded,
    FullJobDetail,
    RawJobListing,
    ScraperStopped,
    absolute_url,
    external_id_from_url,
    extract_skills_from_text,
    html_to_plain_text,
    infer_work_type,
    normalize_space,
    parse_posted_at,
    parse_salary_range_inr,
)

logger = logging.getLogger("autohire.scrapers.wellfound")


class WellfoundScraper(BoardScraper):
    board_name = "wellfound"
    max_daily_scrapes = 20
    min_delay_seconds = 15
    max_delay_seconds = 45
    base_url = "https://wellfound.com"

    async def _get(self, client: httpx.AsyncClient, url: str) -> httpx.Response:
        await self.before_page_load()
        response = await client.get(url, follow_redirects=True)
        if response.status_code in {403, 429}:
            logger.warning(
                "wellfound_blocked",
                extra={"status_code": response.status_code, "url": url},
            )
            await asyncio.sleep(300)
            await self.before_page_load()
            response = await client.get(url, follow_redirects=True)
            if response.status_code in {403, 429}:
                raise ScraperStopped(
                    f"Wellfound stopped after repeated {response.status_code} for {url}"
                )
        response.raise_for_status()
        return response

    async def scrape_listings(
        self,
        target_roles: list[str],
        location: str,
        max_results: int = 50,
    ) -> list[RawJobListing]:
        listings: list[RawJobListing] = []
        seen: set[str] = set()
        async with httpx.AsyncClient(headers=COMMON_HEADERS, timeout=30) as client:
            for role in target_roles:
                for page in range(1, 21):
                    if len(listings) >= max_results:
                        return listings[:max_results]
                    params = {"q": role, "l": location}
                    if page > 1:
                        params["page"] = str(page)
                    url = f"{self.base_url}/jobs?{urlencode(params)}"
                    try:
                        response = await self._get(client, url)
                    except DailyScrapeLimitExceeded:
                        logger.info("wellfound_daily_limit_reached")
                        return listings[:max_results]
                    except ScraperStopped as exc:
                        logger.warning("wellfound_stopped", extra={"reason": str(exc)})
                        return listings[:max_results]

                    page_listings = self._parse_listing_page(response.text, response.url.human_repr())
                    if not page_listings:
                        break
                    for listing in page_listings:
                        if listing.url in seen:
                            continue
                        seen.add(listing.url)
                        listings.append(listing)
                        if len(listings) >= max_results:
                            return listings[:max_results]
                    if len(page_listings) < 10:
                        break
        return listings[:max_results]

    async def extract_job_detail(self, listing: RawJobListing) -> FullJobDetail:
        async with httpx.AsyncClient(headers=COMMON_HEADERS, timeout=30) as client:
            try:
                response = await self._get(client, listing.url)
            except ScraperStopped:
                raise
        soup = BeautifulSoup(response.text, "html.parser")
        title = normalize_space(_first_text(soup, ["h1", "[data-test*='title']", "[data-testid*='title']"]))
        company = normalize_space(
            _first_text(
                soup,
                [
                    "[data-test*='company']",
                    "[data-testid*='company']",
                    "[class*='company']",
                ],
            )
        )
        description_html = _first_html(
            soup,
            [
                "[data-test*='description']",
                "[data-testid*='description']",
                "[class*='description']",
                "main",
                "body",
            ],
        )
        description = html_to_plain_text(description_html) or listing.description or listing.title
        skills = sorted(set(listing.skills_required + extract_skills_from_text(description)))
        salary_min, salary_max = parse_salary_range_inr(listing.salary_range or description)
        posted_at = listing.posted_at or _posted_at_from_soup(soup)
        location = listing.location or _first_text(soup, ["[class*='location']", "[data-test*='location']"])
        location = normalize_space(location) or None
        return FullJobDetail(
            external_id=listing.external_id,
            title=title or listing.title,
            company=company or listing.company,
            url=listing.url,
            location=location,
            work_type=listing.work_type or infer_work_type(f"{location} {description}"),
            posted_at=posted_at,
            salary_range=listing.salary_range,
            salary_min_inr=listing.salary_min_inr or salary_min,
            salary_max_inr=listing.salary_max_inr or salary_max,
            description=description,
            skills_required=skills,
            experience_level=listing.experience_level,
            metadata=listing.metadata,
        )

    def _parse_listing_page(self, html: str, page_url: str) -> list[RawJobListing]:
        soup = BeautifulSoup(html, "html.parser")
        anchors = [
            anchor
            for anchor in soup.find_all("a", href=True)
            if "/jobs/" in str(anchor.get("href")) or "/job/" in str(anchor.get("href"))
        ]
        listings: list[RawJobListing] = []
        seen_urls: set[str] = set()
        for anchor in anchors:
            url = absolute_url(page_url, str(anchor.get("href")))
            if url in seen_urls:
                continue
            seen_urls.add(url)
            card = _nearest_card(anchor)
            text = normalize_space(card.get_text(" ") if card else anchor.get_text(" "))
            title = normalize_space(anchor.get_text(" ")) or _first_text(card, ["h2", "h3", "[class*='title']"])
            if not title or len(title) > 180:
                title = _title_from_card_text(text)
            company = _first_text(
                card,
                [
                    "[data-test*='company']",
                    "[data-testid*='company']",
                    "[class*='company']",
                    "h4",
                ],
            )
            company = normalize_space(company) or _company_from_card_text(text)
            if not title or not company:
                continue
            posted_at = _posted_at_from_soup(card)
            salary_min, salary_max = parse_salary_range_inr(text)
            listings.append(
                RawJobListing(
                    external_id=external_id_from_url(url),
                    title=title[:500],
                    company=company[:255],
                    url=url,
                    location=_location_from_card_text(text),
                    work_type=infer_work_type(text),
                    posted_at=posted_at,
                    salary_range=text if salary_max else None,
                    salary_min_inr=salary_min,
                    salary_max_inr=salary_max,
                    description=text[:1000],
                    skills_required=extract_skills_from_text(text),
                )
            )
        return listings


def _nearest_card(anchor: Tag) -> Tag:
    current: Tag = anchor
    for _ in range(5):
        parent = current.parent
        if not isinstance(parent, Tag):
            return current
        class_text = " ".join(parent.get("class", []))
        if parent.name in {"li", "article"} or "job" in class_text.lower() or "card" in class_text.lower():
            return parent
        current = parent
    return current


def _first_text(root: BeautifulSoup | Tag | None, selectors: list[str]) -> str:
    if root is None:
        return ""
    for selector in selectors:
        element = root.select_one(selector)
        if element:
            text = normalize_space(element.get_text(" "))
            if text:
                return text
    return ""


def _first_html(root: BeautifulSoup | Tag | None, selectors: list[str]) -> str:
    if root is None:
        return ""
    for selector in selectors:
        element = root.select_one(selector)
        if element:
            return str(element)
    return ""


def _posted_at_from_soup(root: BeautifulSoup | Tag | None) -> object:
    if root is None:
        return None
    time_tag = root.find("time")
    if not isinstance(time_tag, Tag):
        return None
    return parse_posted_at(str(time_tag.get("datetime") or time_tag.get_text(" ")))


def _title_from_card_text(text: str) -> str:
    parts = [part.strip(" -|") for part in text.split("  ") if part.strip()]
    return parts[0] if parts else ""


def _company_from_card_text(text: str) -> str:
    parts = [part.strip(" -|") for part in text.split("  ") if part.strip()]
    return parts[1] if len(parts) > 1 else ""


def _location_from_card_text(text: str) -> str | None:
    lowered = text.lower()
    if "remote" in lowered:
        return "Remote"
    known = ["bangalore", "bengaluru", "mumbai", "pune", "delhi", "gurgaon", "hyderabad", "chennai"]
    for city in known:
        if city in lowered:
            return city.title()
    return None
