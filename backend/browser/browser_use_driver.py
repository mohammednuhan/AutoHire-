from __future__ import annotations

import io
import logging
import os
import random
import re
from pathlib import Path
from typing import Any

from PIL import Image

from browser.driver import BrowserDriver
from browser.models import Action, ScreenshotResult
from browser.security import DomainAllowlist
from browser.stealth import (
    apply_stealth,
    random_long_delay,
    random_medium_delay,
    random_scroll_before_click,
    random_short_delay,
)

logger = logging.getLogger("autohire.browser.driver")

SCREENSHOT_MAX_SIZE = (1280, 720)


class BrowserUseDriver(BrowserDriver):
    """Primary browser driver using browser-use 0.12.2."""

    def __init__(self) -> None:
        self.browser: Any | None = None
        self.context: Any | None = None
        self.page: Any | None = None
        self.allowlist = DomainAllowlist()

    async def start(self, headless: bool = True) -> None:
        from browser_use.browser.browser import Browser, BrowserConfig

        config = BrowserConfig(
            headless=headless,
            disable_security=False,
            extra_chromium_args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        self.browser = Browser(config=config)
        self.context = await self.browser.new_context()
        self.page = await self._current_page()
        await self._apply_stealth()
        try:
            await self.allowlist.install_on_page(self.page)
        except Exception as exc:
            logger.info("domain_allowlist_route_unavailable", extra={"error": str(exc)})

    async def navigate(self, url: str) -> ScreenshotResult:
        try:
            if not await self.allowlist.check_navigation(url):
                return await self._result(False, "Blocked by domain allowlist")
            page = await self._current_page()
            await random_long_delay()
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(random.randint(1000, 2500))
            return await self._result(True)
        except Exception as exc:
            return await self._result(False, str(exc))

    async def fill_field(self, field_description: str, value: str) -> ScreenshotResult:
        try:
            instruction = f"Find the input field for {field_description} and type: {value}"
            if await self._try_browser_use_agent(instruction):
                return await self._result(True)
            locator = await self._find_field(field_description)
            await locator.scroll_into_view_if_needed(timeout=5000)
            await random_medium_delay()
            await locator.click(timeout=5000)
            try:
                await locator.fill("", timeout=5000)
            except Exception:
                await self._select_existing_text()
            await self._type_with_human_delay(locator, value)
            return await self._result(True)
        except Exception as exc:
            return await self._result(False, str(exc))

    async def click_element(self, element_description: str) -> ScreenshotResult:
        try:
            instruction = f"Find and click {element_description}"
            if await self._try_browser_use_agent(instruction):
                return await self._result(True)
            locator = await self._find_clickable(element_description)
            await locator.scroll_into_view_if_needed(timeout=5000)
            await random_scroll_before_click(await self._current_page())
            await locator.click(timeout=10000)
            await (await self._current_page()).wait_for_timeout(random.randint(750, 1800))
            return await self._result(True)
        except Exception as exc:
            return await self._result(False, str(exc))

    async def upload_file(self, field_description: str, file_path: str) -> ScreenshotResult:
        try:
            path = str(Path(file_path).resolve())
            instruction = f"Find the file upload field for {field_description} and upload: {path}"
            if await self._try_browser_use_agent(instruction):
                return await self._result(True)
            locator = await self._find_file_input(field_description)
            await random_medium_delay()
            await locator.set_input_files(path)
            await (await self._current_page()).wait_for_timeout(random.randint(1000, 2400))
            return await self._result(True)
        except Exception as exc:
            return await self._result(False, str(exc))

    async def select_option(self, field_description: str, option_value: str) -> ScreenshotResult:
        try:
            instruction = f"Find the dropdown for {field_description} and select: {option_value}"
            if await self._try_browser_use_agent(instruction):
                return await self._result(True)
            locator = await self._find_select(field_description)
            await locator.scroll_into_view_if_needed(timeout=5000)
            await random_medium_delay()
            try:
                await locator.select_option(label=option_value)
            except Exception:
                await locator.select_option(value=option_value)
            return await self._result(True)
        except Exception as exc:
            return await self._result(False, str(exc))

    async def scroll_page(self, direction: str | None = None) -> ScreenshotResult:
        try:
            page = await self._current_page()
            delta = -550 if direction and direction.lower() in {"up", "top"} else 550
            await page.mouse.wheel(0, delta)
            await page.wait_for_timeout(random.randint(500, 1600))
            return await self._result(True)
        except Exception as exc:
            return await self._result(False, str(exc))

    async def take_screenshot(self) -> bytes:
        page = await self._current_page()
        raw = await page.screenshot(full_page=False)
        img = Image.open(io.BytesIO(raw))
        img.thumbnail(SCREENSHOT_MAX_SIZE, Image.LANCZOS)
        if img.mode not in {"RGB", "RGBA"}:
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    async def css_fallback(self, action: Action) -> ScreenshotResult | None:
        if not action.selector:
            return None
        try:
            page = await self._current_page()
            locator = page.locator(action.selector).first()
            if action.action == "fill":
                await locator.fill(action.value or "")
            elif action.action == "click" or action.action == "checkbox":
                await locator.click()
            elif action.action == "select":
                await locator.select_option(label=action.option_value or action.value or "")
            elif action.action == "upload":
                await locator.set_input_files(str(Path(action.file_path or "").resolve()))
            else:
                return None
            return await self._result(True)
        except Exception as exc:
            return await self._result(False, str(exc))

    async def close(self) -> None:
        if self.browser is not None:
            await self.browser.close()
        self.browser = None
        self.context = None
        self.page = None

    async def _current_page(self) -> Any:
        if self.context is not None and hasattr(self.context, "get_current_page"):
            self.page = await self.context.get_current_page()
            return self.page
        if self.page is not None:
            return self.page
        raise RuntimeError("Browser has not been started")

    async def _result(self, success: bool, error: str | None = None) -> ScreenshotResult:
        try:
            screenshot = await self.take_screenshot()
        except Exception as screenshot_error:
            screenshot = b""
            error = error or f"screenshot failed: {screenshot_error}"
            success = False
        return ScreenshotResult(success=success, screenshot_bytes=screenshot, error=error)

    async def _apply_stealth(self) -> None:
        try:
            await apply_stealth(await self._current_page())
        except Exception as exc:
            logger.info("playwright_stealth_unavailable", extra={"error": str(exc)})

    async def _try_browser_use_agent(self, instruction: str) -> bool:
        if os.getenv("BROWSER_USE_AGENT_MODE", "1") != "1":
            return False
        try:
            from browser_use import Agent as BrowserAgent

            kwargs: dict[str, Any] = {"task": instruction, "browser": self.browser}
            if self.context is not None:
                kwargs["browser_context"] = self.context
            agent = BrowserAgent(**kwargs)
            await agent.run()
            await (await self._current_page()).wait_for_timeout(500)
            return True
        except Exception as exc:
            logger.debug("browser_use_agent_fallback", extra={"error": str(exc)})
            return False

    async def _find_field(self, description: str) -> Any:
        page = await self._current_page()
        pattern = re.compile(re.escape(description), re.IGNORECASE)
        locators = [
            page.get_by_label(pattern),
            page.get_by_placeholder(pattern),
            page.get_by_role("textbox", name=pattern),
            page.locator("input:not([type=hidden]), textarea, [contenteditable=true]"),
        ]
        return await self._first_visible(locators)

    async def _find_clickable(self, description: str) -> Any:
        page = await self._current_page()
        pattern = re.compile(re.escape(description), re.IGNORECASE)
        locators = [
            page.get_by_role("button", name=pattern),
            page.get_by_role("link", name=pattern),
            page.get_by_text(pattern),
            page.locator("button, a, input[type=button], input[type=submit], [role=button]"),
        ]
        return await self._first_visible(locators)

    async def _find_file_input(self, description: str) -> Any:
        page = await self._current_page()
        pattern = re.compile(re.escape(description), re.IGNORECASE)
        locators = [
            page.get_by_label(pattern).locator("input[type=file]"),
            page.locator("input[type=file]"),
        ]
        return await self._first_attached(locators)

    async def _find_select(self, description: str) -> Any:
        page = await self._current_page()
        pattern = re.compile(re.escape(description), re.IGNORECASE)
        locators = [
            page.get_by_label(pattern),
            page.locator("select"),
        ]
        return await self._first_visible(locators)

    async def _first_visible(self, locators: list[Any]) -> Any:
        for locator in locators:
            try:
                count = await locator.count()
                for index in range(min(count, 8)):
                    candidate = locator.nth(index)
                    if await candidate.is_visible(timeout=1000):
                        return candidate
            except Exception:
                continue
        raise RuntimeError("No visible element matched the requested description")

    async def _first_attached(self, locators: list[Any]) -> Any:
        for locator in locators:
            try:
                count = await locator.count()
                if count:
                    return locator.first()
            except Exception:
                continue
        raise RuntimeError("No attached element matched the requested description")

    async def _select_existing_text(self) -> None:
        page = await self._current_page()
        control = "Meta+A" if os.name == "posix" else "Control+A"
        await page.keyboard.press(control)

    async def _type_with_human_delay(self, element: Any, text: str) -> None:
        for char in text:
            await element.type(char)
            await random_short_delay()
