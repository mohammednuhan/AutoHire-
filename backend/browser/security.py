from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

from browser.state_machine import publish_ws_event

logger = logging.getLogger("autohire.browser.security")


class DomainAllowlist:
    """
    Playwright can only navigate to pre-approved domains.
    Prevents accidental credential exposure via malicious redirects.
    """

    DEFAULT_ALLOWED = [
        "wellfound.com",
        "internshala.com",
        "naukri.com",
        "foundit.in",
        "cutshort.io",
        "instahyre.com",
        "zerodha.com",
        "razorpay.com",
        "cred.club",
        "swiggy.com",
        "zomato.com",
        "phonepe.com",
        "groww.in",
        "meesho.io",
        "freshworks.com",
    ]

    def __init__(self, extra_allowed: list[str] | None = None) -> None:
        self.allowed = [domain.lower().lstrip("www.") for domain in self.DEFAULT_ALLOWED]
        if extra_allowed:
            self.allowed.extend(domain.lower().lstrip("www.") for domain in extra_allowed)

    async def check_navigation(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme in {"about", "data", "blob"}:
            return True
        domain = parsed.netloc.lower().lstrip("www.")
        if not domain:
            return True
        if not any(allowed == domain or domain.endswith(f".{allowed}") for allowed in self.allowed):
            await publish_ws_event(
                "ERROR",
                error_code="BLOCKED_NAVIGATION",
                message=f"Agent attempted to navigate to unauthorized domain: {domain}",
            )
            logger.warning("blocked_navigation", extra={"domain": domain, "url": url})
            return False
        return True

    async def install_on_page(self, page: Any) -> None:
        async def route_handler(route: Any) -> None:
            if await self.check_navigation(route.request.url):
                await route.continue_()
            else:
                await route.abort()

        await page.route("**/*", route_handler)
