from __future__ import annotations

import logging

from scrapers.base import BoardScraper, FullJobDetail, RawJobListing

logger = logging.getLogger("autohire.scrapers.stubs")


class PhaseTwoStubScraper(BoardScraper):
    max_daily_scrapes = 0
    min_delay_seconds = 0
    max_delay_seconds = 0

    async def scrape_listings(
        self,
        target_roles: list[str],
        location: str,
        max_results: int = 50,
    ) -> list[RawJobListing]:
        logger.info("%s_scraper_stubbed", self.board_name)
        return []

    async def extract_job_detail(self, listing: RawJobListing) -> FullJobDetail:
        raise NotImplementedError(f"{self.board_name} is Phase 2 and is stubbed in v1")


class NaukriScraper(PhaseTwoStubScraper):
    board_name = "naukri"


class FounditScraper(PhaseTwoStubScraper):
    board_name = "foundit"


class CutshortScraper(PhaseTwoStubScraper):
    board_name = "cutshort"
