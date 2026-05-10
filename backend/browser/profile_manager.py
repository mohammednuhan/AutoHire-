from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from storage import data_dir
from notifications.telegram import send_health_alert

logger = logging.getLogger("autohire.browser.profile_manager")


class BrowserProfileManager:
    """
    Manages persistent browser profiles per job board.
    Login once manually, then reuse the saved profile on future runs.
    """

    def __init__(self) -> None:
        self.profiles_dir = data_dir() / "browser_profiles"
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    async def get_profile_path(self, board: str) -> Path:
        path = self.profiles_dir / board.strip().lower()
        path.mkdir(parents=True, exist_ok=True)
        return path

    async def save_profile(self, board: str, browser_context: Any) -> None:
        path = await self.get_profile_path(board)
        storage_state = await browser_context.storage_state()
        (path / "storage_state.json").write_text(json.dumps(storage_state, indent=2))
        (path / "profile_saved").write_text("ok")
        logger.info("browser_profile_saved", extra={"board": board, "path": str(path)})

    async def load_profile(self, board: str) -> dict[str, Any]:
        path = await self.get_profile_path(board)
        state_path = path / "storage_state.json"
        options: dict[str, Any] = {"user_data_dir": str(path)}
        if state_path.exists():
            options["storage_state"] = json.loads(state_path.read_text())
        return options

    async def is_profile_valid(self, board: str) -> bool:
        path = await self.get_profile_path(board)
        if not (path / "profile_saved").exists():
            await send_health_alert("Browser profile", f"{board} profile needs first-time login")
            return False
        # A live protected-page check requires site-specific URLs and a browser launch.
        # For v1 hardening we treat the persisted marker and storage state as the fast path;
        # scrapers will still detect login redirects and notify the user at runtime.
        valid = (path / "storage_state.json").exists()
        if not valid:
            await send_health_alert("Browser profile", f"{board} profile expired or missing storage state")
        return valid
