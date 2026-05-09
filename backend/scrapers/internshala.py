from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import quote

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

logger = logging.getLogger("autohire.scrapers.internshala")


class InternshalaScraper(BoardScraper):
    board_name = "internshala"
    max_daily_scrapes = 20
    min_delay_seconds = 20
    max_delay_seconds = 60
    base_url = "https://internshala.com"

    async def _get(self, client: httpx.AsyncClient, url: str) -> httpx.Response:
        await self.before_page_load()
        response = await client.get(url, follow_redirects=True)
        if response.status_code in {403, 429}:
            logger.warning(
                "internshala_blocked",
                extra={"status_code": response.status_code, "url": url},
            )
            await asyncio.sleep(300)
            await self.before_page_load()
            response = await client.get(url, follow_redirects=True)
            if response.status_code in {403, 429}:
                raise ScraperStopped(
                    f"Internshala stopped after repeated {response.status_code} for {url}"
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
                slug = quote(role.strip().replace(" ", "-"))
                paths = [f"/jobs/keywords-{slug}", f"/internships/keywords-{slug}"]
                for path in paths:
                    if len(listings) >= max_results:
                        return listings[:max_results]
                    url = f"{self.base_url}{path}"
                    try:
                        response = await self._get(client, url)
                    except DailyScrapeLimitExceeded:
                        logger.info("internshala_daily_limit_reached")
                        return listings[:max_results]
                    except ScraperStopped as exc:
                        logger.warning("internshala_stopped", extra={"reason": str(exc)})
                        return listings[:max_results]
                    page_listings = self._parse_response(response)
                    for listing in page_listings:
                        if listing.url in seen:
                            continue
                        seen.add(listing.url)
                        if location and location.lower() not in {"india", "any"}:
                            listing_text = f"{listing.location or ''} {listing.description or ''}".lower()
                            if location.lower() not in listing_text and "remote" not in listing_text:
                                continue
                        listings.append(listing)
                        if len(listings) >= max_results:
                            return listings[:max_results]
        return listings[:max_results]

    async def extract_job_detail(self, listing: RawJobListing) -> FullJobDetail:
        detail_url = listing.url or f"{self.base_url}/internship/detail/{listing.external_id}"
        async with httpx.AsyncClient(headers=COMMON_HEADERS, timeout=30) as client:
            response = await self._get(client, detail_url)

        payload = _json_or_none(response)
        if payload is not None:
            detail = _detail_from_json(payload, listing, detail_url)
            if detail:
                return detail

        soup = BeautifulSoup(response.text, "html.parser")
        description_html = _first_html(
            soup,
            [
                "#details_container",
                ".internship_details",
                ".job_details",
                "[class*='detail']",
                "main",
                "body",
            ],
        )
        description = html_to_plain_text(description_html) or listing.description or listing.title
        title = _first_text(soup, ["h1", ".profile_on_detail_page", "[class*='profile']"]) or listing.title
        company = _first_text(soup, [".company_name", "[class*='company']"]) or listing.company
        location = _first_text(soup, [".location_link", "[class*='location']"]) or listing.location
        stipend = _first_text(soup, [".stipend", "[class*='salary']", "[class*='stipend']"])
        salary_min, salary_max = parse_salary_range_inr(stipend or description)
        skills = sorted(set(listing.skills_required + extract_skills_from_text(description)))
        return FullJobDetail(
            external_id=listing.external_id,
            title=normalize_space(title)[:500],
            company=normalize_space(company)[:255],
            url=detail_url,
            location=normalize_space(location) or None,
            work_type=listing.work_type or infer_work_type(f"{location} {description}"),
            posted_at=listing.posted_at,
            salary_range=stipend or listing.salary_range,
            salary_min_inr=listing.salary_min_inr or salary_min,
            salary_max_inr=listing.salary_max_inr or salary_max,
            description=description,
            skills_required=skills,
            experience_level=listing.experience_level,
            metadata=listing.metadata,
        )

    def _parse_response(self, response: httpx.Response) -> list[RawJobListing]:
        payload = _json_or_none(response)
        if payload is not None:
            return _listings_from_json(payload, self.base_url)
        return _listings_from_html(response.text, response.url.human_repr())


def _json_or_none(response: httpx.Response) -> Any | None:
    content_type = response.headers.get("content-type", "")
    if "json" not in content_type and not response.text.lstrip().startswith(("{", "[")):
        return None
    try:
        return response.json()
    except ValueError:
        return None


def _listings_from_json(payload: Any, base_url: str) -> list[RawJobListing]:
    listings: list[RawJobListing] = []
    for item in _candidate_dicts(payload):
        title = _value(item, "title", "profile_name", "job_title")
        company = _value(item, "company", "company_name", "employer_name")
        external_value = _value(item, "id", "internship_id", "job_id", "employment_id")
        if not title or not company or not external_value:
            continue
        external_id = str(external_value)
        path = _value(item, "url", "job_url", "internship_url", "detail_url")
        detail_url = absolute_url(base_url, path) if path else f"{base_url}/internship/detail/{external_id}"
        location = _location_value(item.get("location_names") or item.get("locations") or item.get("location"))
        salary_text = str(_value(item, "stipend", "salary", "salary_range", "ctc") or "")
        salary_min, salary_max = parse_salary_range_inr(salary_text)
        text = " ".join(
            str(value)
            for value in [
                title,
                company,
                location,
                salary_text,
                item.get("skills_required"),
                item.get("skills"),
                item.get("description"),
            ]
            if value
        )
        listings.append(
            RawJobListing(
                external_id=external_id[:500],
                title=normalize_space(str(title))[:500],
                company=normalize_space(str(company))[:255],
                url=detail_url,
                location=normalize_space(location) or None,
                work_type=infer_work_type(text),
                posted_at=parse_posted_at(str(_value(item, "posted_at", "posted_on", "start_date") or "")),
                salary_range=salary_text or None,
                salary_min_inr=salary_min,
                salary_max_inr=salary_max,
                description=normalize_space(str(item.get("description") or ""))[:1000] or None,
                skills_required=_skills_value(item.get("skills_required") or item.get("skills") or text),
                metadata={"duration": _value(item, "duration"), "start_date": _value(item, "start_date")},
            )
        )
    return listings


def _candidate_dicts(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        keys = {key.lower() for key in value}
        has_title = bool(keys & {"title", "profile_name", "job_title"})
        has_company = bool(keys & {"company", "company_name", "employer_name"})
        has_id = bool(keys & {"id", "internship_id", "job_id", "employment_id"})
        if has_title and has_company and has_id:
            found.append(value)
        for child in value.values():
            found.extend(_candidate_dicts(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_candidate_dicts(child))
    return found


def _listings_from_html(html: str, page_url: str) -> list[RawJobListing]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(".individual_internship, [internshipid], [data-job-id], [class*='job']")
    listings: list[RawJobListing] = []
    seen: set[str] = set()
    for card in cards:
        if not isinstance(card, Tag):
            continue
        title = _first_text(card, [".profile", ".job-title-href", "h3", "h2", "[class*='title']"])
        company = _first_text(card, [".company_name", "[class*='company']"])
        link = card.find("a", href=True)
        if not isinstance(link, Tag) or not title or not company:
            continue
        url = absolute_url(page_url, str(link.get("href")))
        if url in seen:
            continue
        seen.add(url)
        text = normalize_space(card.get_text(" "))
        salary_text = _first_text(card, [".stipend", "[class*='salary']", "[class*='stipend']"])
        salary_min, salary_max = parse_salary_range_inr(salary_text or text)
        external_id = str(card.get("internshipid") or card.get("data-job-id") or external_id_from_url(url))
        listings.append(
            RawJobListing(
                external_id=external_id[:500],
                title=normalize_space(title)[:500],
                company=normalize_space(company)[:255],
                url=url,
                location=_first_text(card, [".locations", ".location_link", "[class*='location']"]) or None,
                work_type=infer_work_type(text),
                posted_at=parse_posted_at(_first_text(card, [".status-success", "time"])),
                salary_range=salary_text or None,
                salary_min_inr=salary_min,
                salary_max_inr=salary_max,
                description=text[:1000],
                skills_required=extract_skills_from_text(text),
            )
        )
    return listings


def _detail_from_json(payload: Any, listing: RawJobListing, detail_url: str) -> FullJobDetail | None:
    candidates = _candidate_dicts(payload)
    item = candidates[0] if candidates else payload if isinstance(payload, dict) else None
    if not isinstance(item, dict):
        return None
    description = html_to_plain_text(
        str(_value(item, "description", "job_description", "internship_description", "details") or "")
    )
    if not description:
        return None
    salary_text = str(_value(item, "stipend", "salary", "salary_range", "ctc") or listing.salary_range or "")
    salary_min, salary_max = parse_salary_range_inr(salary_text)
    skills = sorted(set(listing.skills_required + _skills_value(item.get("skills_required") or item.get("skills") or description)))
    return FullJobDetail(
        external_id=listing.external_id,
        title=normalize_space(str(_value(item, "title", "profile_name", "job_title") or listing.title))[:500],
        company=normalize_space(str(_value(item, "company", "company_name", "employer_name") or listing.company))[:255],
        url=detail_url,
        location=normalize_space(_location_value(item.get("location_names") or item.get("locations") or item.get("location")) or listing.location or "") or None,
        work_type=listing.work_type or infer_work_type(description),
        posted_at=listing.posted_at,
        salary_range=salary_text or None,
        salary_min_inr=listing.salary_min_inr or salary_min,
        salary_max_inr=listing.salary_max_inr or salary_max,
        description=description,
        skills_required=skills,
        experience_level=listing.experience_level,
        metadata=listing.metadata,
    )


def _value(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = item.get(key)
        if value is not None and value != "":
            return value
    return None


def _location_value(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(part.get("name", part)) if isinstance(part, dict) else str(part) for part in value)
    if isinstance(value, dict):
        return str(value.get("name") or value.get("city") or "")
    return str(value or "")


def _skills_value(value: Any) -> list[str]:
    if isinstance(value, list):
        return [normalize_space(str(skill)) for skill in value if normalize_space(str(skill))]
    if isinstance(value, str):
        extracted = extract_skills_from_text(value)
        if extracted:
            return extracted
        return [normalize_space(part) for part in value.split(",") if normalize_space(part)]
    return []


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
