from scrapers.base import BoardScraper, FullJobDetail, RawJobListing
from scrapers.career_pages import CareerPageScraper
from scrapers.foundit import FounditScraper
from scrapers.internshala import InternshalaScraper
from scrapers.naukri import NaukriScraper
from scrapers.stubs import CutshortScraper
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
