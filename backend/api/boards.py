from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.auth import get_current_user
from browser.profile_manager import BrowserProfileManager
from browser.security import DomainAllowlist
from browser.stealth import apply_stealth, browser_context_options
from database.models import User

router = APIRouter(tags=["boards"])
logger = logging.getLogger("autohire.api.boards")

BOARD_LOGIN_URLS = {
    "naukri": "https://www.naukri.com/nlogin/login",
    "foundit": "https://www.foundit.in/seeker/login",
}


class BoardLoginRequest(BaseModel):
    wait_seconds: int = Field(default=180, ge=30, le=900)


@router.post("/api/boards/{board}/login", response_model=dict[str, str])
async def login_board(
    board: str,
    payload: BoardLoginRequest,
    _current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    board_key = board.strip().lower()
    login_url = BOARD_LOGIN_URLS.get(board_key)
    if login_url is None:
        return {"status": "unsupported_board", "board": board_key}

    from playwright.async_api import async_playwright

    manager = BrowserProfileManager()
    profile = await manager.load_profile(board_key)
    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=profile["user_data_dir"],
            headless=False,
            **browser_context_options(),
        )
        page = await context.new_page()
        await apply_stealth(page)
        await DomainAllowlist().install_on_page(page)
        await page.goto(login_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(payload.wait_seconds * 1000)
        await manager.save_profile(board_key, context)
        await context.close()
    return {"status": "profile_saved", "board": board_key}
