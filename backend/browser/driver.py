from __future__ import annotations

from abc import ABC, abstractmethod

from browser.models import ScreenshotResult


class BrowserDriver(ABC):
    """Abstraction layer over browser-use. Swap implementations without changing agent logic."""

    @abstractmethod
    async def start(self, headless: bool = True) -> None:
        ...

    @abstractmethod
    async def navigate(self, url: str) -> ScreenshotResult:
        ...

    @abstractmethod
    async def fill_field(self, field_description: str, value: str) -> ScreenshotResult:
        ...

    @abstractmethod
    async def click_element(self, element_description: str) -> ScreenshotResult:
        ...

    @abstractmethod
    async def upload_file(self, field_description: str, file_path: str) -> ScreenshotResult:
        ...

    @abstractmethod
    async def select_option(self, field_description: str, option_value: str) -> ScreenshotResult:
        ...

    @abstractmethod
    async def take_screenshot(self) -> bytes:
        """Always returns screenshot bytes resized to max 1280x720."""
        ...

    @abstractmethod
    async def close(self) -> None:
        ...
