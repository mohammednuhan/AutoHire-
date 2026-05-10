# Contributing to AutoHire

## Adding a Job Board

AutoHire supports two scraper styles.

### Method 1: HTTP-first scraper

Use this when listings are public HTML or JSON.

1. Create `backend/scrapers/<board>.py`.
2. Subclass `BoardScraper`.
3. Implement `scrape_listings()` and `extract_job_detail()`.
4. Respect `max_daily_scrapes`, `min_delay_seconds`, and `max_delay_seconds`.
5. Add the class to `backend/scrapers/__init__.py`.
6. Register it in `SUPPORTED_SCRAPERS` in `backend/agent/scanner.py`.

### Method 2: Playwright profile scraper

Use this for boards that require login.

1. Use `BrowserProfileManager` to load a persistent profile.
2. Add a login URL to `BOARD_LOGIN_URLS` in `backend/api/boards.py`.
3. Use `DomainAllowlist` and `apply_stealth()` on every page.
4. Never bypass CAPTCHA or platform rate limits.

## Checks

```bash
cd backend
pytest tests/ -v
ruff check .

cd ../frontend
npm run typecheck
npm run lint
```

## Backlog Labels

Open GitHub issues for:
- A/B testing
- Skills graph
- Interview prep
- Learning engine
