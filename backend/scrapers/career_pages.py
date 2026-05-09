from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag

from scrapers.base import (
    COMMON_HEADERS,
    BoardScraper,
    FullJobDetail,
    RawJobListing,
    absolute_url,
    external_id_from_url,
    extract_skills_from_text,
    html_to_plain_text,
    infer_work_type,
    normalize_space,
    parse_posted_at,
    parse_salary_range_inr,
)

logger = logging.getLogger("autohire.scrapers.career_pages")


COMPANY_CAREER_PAGES = {
    "Zerodha": "https://zerodha.com/jobs",
    "Razorpay": "https://razorpay.com/jobs",
    "CRED": "https://careers.cred.club",
    "Swiggy": "https://careers.swiggy.com",
    "Zomato": "https://www.zomato.com/careers",
    "PhonePe": "https://careers.phonepe.com",
    "Groww": "https://groww.in/careers",
    "Meesho": "https://meesho.io/jobs",
    "Freshworks": "https://www.freshworks.com/company/careers",
}


class CareerPageScraper(BoardScraper):
    board_name = "career_page"
    max_daily_scrapes = 1000
    min_delay_seconds = 0
    max_delay_seconds = 0

    async def scrape_listings(
        self,
        target_roles: list[str],
        location: str,
        max_results: int = 50,
    ) -> list[RawJobListing]:
        listings: list[RawJobListing] = []
        seen: set[str] = set()
        async with httpx.AsyncClient(headers=COMMON_HEADERS, timeout=30) as client:
            for company, url in COMPANY_CAREER_PAGES.items():
                if len(listings) >= max_results:
                    break
                try:
                    await self.before_page_load()
                    response = await client.get(url, follow_redirects=True)
                    response.raise_for_status()
                except Exception as exc:
                    logger.info("career_page_fetch_failed", extra={"company": company, "error": str(exc)})
                    continue
                page_listings = self._parse_page(company, response.text, response.url.human_repr())
                for listing in page_listings:
                    if listing.url in seen:
                        continue
                    if not _matches_targets(listing, target_roles, location):
                        continue
                    seen.add(listing.url)
                    listings.append(listing)
                    if len(listings) >= max_results:
                        break
        return listings[:max_results]

    async def extract_job_detail(self, listing: RawJobListing) -> FullJobDetail:
        async with httpx.AsyncClient(headers=COMMON_HEADERS, timeout=30) as client:
            try:
                await self.before_page_load()
                response = await client.get(listing.url, follow_redirects=True)
                response.raise_for_status()
            except Exception:
                description = listing.description or listing.title
            else:
                soup = BeautifulSoup(response.text, "html.parser")
                description_html = _first_html(
                    soup,
                    [
                        "[class*='job-description']",
                        "[class*='description']",
                        "[class*='content']",
                        "main",
                        "body",
                    ],
                )
                description = html_to_plain_text(description_html) or listing.description or listing.title
        salary_min, salary_max = parse_salary_range_inr(description)
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

    def _parse_page(self, company: str, html: str, page_url: str) -> list[RawJobListing]:
        soup = BeautifulSoup(html, "html.parser")
        listings = _json_ld_listings(company, soup, page_url)
        listings.extend(_anchor_listings(company, soup, page_url))
        unique: dict[str, RawJobListing] = {}
        for listing in listings:
            unique.setdefault(listing.url, listing)
        return list(unique.values())


def _json_ld_listings(company: str, soup: BeautifulSoup, page_url: str) -> list[RawJobListing]:
    listings: list[RawJobListing] = []
    for script in soup.select("script[type='application/ld+json']"):
        try:
            payload = json.loads(script.string or script.get_text() or "{}")
        except json.JSONDecodeError:
            continue
        for item in _jobposting_nodes(payload):
            title = normalize_space(str(item.get("title") or item.get("name") or ""))
            if not title:
                continue
            org = item.get("hiringOrganization") or {}
            item_company = normalize_space(str(org.get("name") if isinstance(org, dict) else company)) or company
            url = absolute_url(page_url, str(item.get("url") or item.get("sameAs") or page_url))
            description = html_to_plain_text(str(item.get("description") or ""))
            location = _json_ld_location(item.get("jobLocation"))
            salary_min, salary_max = parse_salary_range_inr(description)
            listings.append(
                RawJobListing(
                    external_id=external_id_from_url(url),
                    title=title[:500],
                    company=item_company[:255],
                    url=url,
                    location=location,
                    work_type=infer_work_type(f"{location} {description}"),
                    posted_at=parse_posted_at(str(item.get("datePosted") or "")),
                    salary_min_inr=salary_min,
                    salary_max_inr=salary_max,
                    description=description[:1000] or None,
                    skills_required=extract_skills_from_text(description),
                )
            )
    return listings


def _anchor_listings(company: str, soup: BeautifulSoup, page_url: str) -> list[RawJobListing]:
    listings: list[RawJobListing] = []
    selectors = [
        ".job-title",
        ".position-name",
        ".role-title",
        ".job-listing",
        "[class*='job-title']",
        "[class*='position']",
        "[class*='role']",
        "[class*='job-listing']",
    ]
    for element in soup.select(", ".join(selectors)):
        card = element if isinstance(element, Tag) else None
        if card is None:
            continue
        anchor = card if card.name == "a" else card.find("a", href=True)
        if not isinstance(anchor, Tag):
            continue
        listing = _listing_from_anchor(company, anchor, card, page_url)
        if listing:
            listings.append(listing)

    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "").lower()
        text = normalize_space(anchor.get_text(" "))
        if not any(token in href for token in ("apply", "job", "position", "career")):
            continue
        if not text or len(text) > 160:
            continue
        listing = _listing_from_anchor(company, anchor, anchor, page_url)
        if listing:
            listings.append(listing)
    return listings


def _listing_from_anchor(company: str, anchor: Tag, card: Tag, page_url: str) -> RawJobListing | None:
    url = absolute_url(page_url, str(anchor.get("href") or ""))
    title = normalize_space(anchor.get_text(" ") or card.get_text(" "))
    if not title or title.lower() in {"apply", "view job", "jobs", "careers"}:
        return None
    text = normalize_space(card.get_text(" "))
    salary_min, salary_max = parse_salary_range_inr(text)
    return RawJobListing(
        external_id=external_id_from_url(url),
        title=title[:500],
        company=company,
        url=url,
        location=_known_location(text),
        work_type=infer_work_type(text),
        salary_range=text if salary_max else None,
        salary_min_inr=salary_min,
        salary_max_inr=salary_max,
        description=text[:1000],
        skills_required=extract_skills_from_text(text),
    )


def _jobposting_nodes(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        node_type = value.get("@type")
        node_types = node_type if isinstance(node_type, list) else [node_type]
        if any(str(item).lower() == "jobposting" for item in node_types):
            found.append(value)
        for child in value.values():
            found.extend(_jobposting_nodes(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_jobposting_nodes(child))
    return found


def _json_ld_location(value: Any) -> str | None:
    if isinstance(value, list):
        return ", ".join(filter(None, (_json_ld_location(item) for item in value))) or None
    if isinstance(value, dict):
        address = value.get("address")
        if isinstance(address, dict):
            parts = [address.get("addressLocality"), address.get("addressRegion"), address.get("addressCountry")]
            return ", ".join(str(part) for part in parts if part) or None
        return normalize_space(str(value.get("name") or ""))
    return normalize_space(str(value or "")) or None


def _known_location(text: str) -> str | None:
    lowered = text.lower()
    for city in ["bengaluru", "bangalore", "mumbai", "pune", "delhi", "gurgaon", "hyderabad", "chennai"]:
        if city in lowered:
            return city.title()
    if "remote" in lowered:
        return "Remote"
    return None


def _first_html(root: BeautifulSoup | Tag | None, selectors: list[str]) -> str:
    if root is None:
        return ""
    for selector in selectors:
        element = root.select_one(selector)
        if element:
            return str(element)
    return ""


def _matches_targets(listing: RawJobListing, target_roles: list[str], location: str) -> bool:
    haystack = f"{listing.title} {listing.description or ''}".lower()
    role_match = not target_roles or any(role.lower() in haystack for role in target_roles)
    if not role_match:
        return False
    if location.lower() in {"", "india", "any"}:
        return True
    listing_location = f"{listing.location or ''} {listing.description or ''}".lower()
    return location.lower() in listing_location or "remote" in listing_location
