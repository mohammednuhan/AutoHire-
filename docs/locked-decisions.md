# Locked Decisions

These decisions are part of the AutoHire foundation and must not be changed casually.

1. Python version: 3.12.
2. Package manager: uv.
3. Database driver: asyncpg.
4. ORM: SQLAlchemy 2.0 async with Alembic.
5. Browser layer: browser-use 0.12.2.
6. LLM default dev: Gemini 2.0 Flash.
7. LLM default prod: claude-sonnet-4-6.
8. Extended thinking: only for cover letter generation and complex screening answers.
9. Scheduling: APScheduler AsyncIOScheduler with CronTrigger and `USER_TIMEZONE`.
10. Single-user v1 only.
11. Score auto-queue default: `>= 70`.
12. Confidence gate: `< 0.80` means `NEEDS_HUMAN`.
13. Daily application cap: 10, user-adjustable, max 30.
14. Dream company: always `NEEDS_HUMAN`.
15. LinkedIn: Phase 3 only, max 5/day, semi-automatic only.
16. Stop button: Redis key `STOP_REQUESTED=1`, checked before every agent action.
17. Redis lock: TTL 2 hours, heartbeat renewed every 15 minutes.
18. Cover letter: 200-300 words, 3 paragraphs, no generic phrases.
19. Resume: single-column text only, no tables, no graphics.
20. Screenshot cap: 1280x720 before sending to any vision LLM.
21. Agent Docker service must use `shm_size: 2gb`.
22. Backups: weekly `pg_dump`, keep 4 weeks.
23. Session recording: not in v1.
24. Skills graph: not in v1.
25. A/B testing: not in v1.
