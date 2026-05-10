# AutoHire

**AutoHire - Built to get you hired, not ignored.**

Self-hosted, India-first job application agent for tech freshers. AutoHire scans job boards, scores jobs against your real resume, generates verified cover letters, tailors ATS resumes, fills forms in a browser, and pauses whenever human judgment is required.

`demo.gif placeholder`

## Important Disclaimer

AutoHire automates browser interactions to help manage job applications. You are responsible for compliance with each platform's Terms of Service. Use responsibly and at your own discretion. The authors are not liable for account restrictions resulting from automated usage. Built-in rate limits are enforced to minimize detection risk - do not attempt to bypass them.

## What It Does

- Parses your resume into a structured profile.
- Scans supported job boards and company career pages.
- Scores jobs against your actual profile and preferences.
- Generates fact-checked cover letters and tailored ATS resumes.
- Fills application forms in a real browser with audit screenshots and human gates.

## Why It Is Different

| Product | Self-hosted | India-first boards | Fact-checked letters | Human gates | Audit trail |
| --- | --- | --- | --- | --- | --- |
| AutoHire | Yes | Yes | Yes | Yes | Yes |
| LazyApply | No | Limited | No | Limited | Limited |
| JobCopilot | No | Limited | Partial | Partial | Limited |
| Simplify | No | No | No | Partial | Limited |

## Quick Start

```bash
git clone https://github.com/yourname/autohire
cd autohire
cp .env.example .env
# Fill GEMINI_API_KEY, SECRET_KEY, POSTGRES_PASSWORD, and optional Telegram settings
docker compose up --build
```

Open `http://localhost:3000`.

## Configuration

Required:
- `DATABASE_URL`
- `POSTGRES_PASSWORD`
- `REDIS_URL`
- `SECRET_KEY`
- `NEXTAUTH_SECRET`
- At least one LLM key: `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, or `OLLAMA_BASE_URL`

Optional:
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- `SENTRY_DSN`, `NEXT_PUBLIC_SENTRY_DSN`
- `GITHUB_TOKEN`, `GITHUB_REPO`
- `USER_TIMEZONE`, `SCHEDULE_CRON`, `MORNING_DIGEST_CRON`

## Job Boards

| Phase | Boards | Status |
| --- | --- | --- |
| Phase 1 | Wellfound, Internshala, company career pages | Supported |
| Phase 2 | Naukri, Foundit | Supported with saved browser profiles and strict rate limits |
| Phase 3 | LinkedIn | Not automated in v1 |

## How It Works

```text
Resume upload
    |
    v
Profile + preferences
    |
    v
Scan boards -> score jobs -> queue applications
    |
    v
Company research -> cover letter -> fact-check
    |
    v
Tailor resume PDF/DOCX
    |
    v
Browser planner -> actor -> validator
    |
    +--> confidence < 0.80 or dream company -> NEEDS_HUMAN
    |
    v
Ready to submit -> user reviews -> final submit
```

## Security

- Self-hosted: resumes, screenshots, and answers stay on your machine.
- Domain allowlist blocks unexpected navigation.
- Prompt-injection patterns are stripped or rejected before LLM calls.
- STOP button is checked before every browser action.
- Screenshots are capped at 1280x720 before vision validation.

## Contributing

See `CONTRIBUTING.md`.

Two scraper methods are supported:
- HTTP-first scraper for public listing pages.
- Playwright profile scraper for login/session-based boards.

## Roadmap

v1.1:
- More Indian startup career pages.
- Better application analytics.
- Manual follow-up workflow.

v2.0:
- Skills graph.
- Interview prep.
- Learning engine.
- A/B testing for cover letter quality.

## License

MIT
