from scrapers.base import BoardScraper, FullJobDetail, RawJobListing
from scrapers.career_pages import CareerPageScraper
from scrapers.internshala import InternshalaScraper
from scrapers.stubs import CutshortScraper, FounditScraper, NaukriScraper
from scrapers.wellfound import WellfoundScraper

__all__ = [
    "BoardScraper",
    "CareerPageScraper",
    "CutshortScraper",
    "FounditScraper",
    "FullJobDetail",
    "InternshalaScraper",
    "NaukriScraper",
    "RawJobListing",
    "WellfoundScraper",
]
