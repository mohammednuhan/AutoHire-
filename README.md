# AutoHire

Open-source, self-hosted autonomous job application agent for Indian tech students and freshers.

This repository is currently at the foundation stage only. It defines infrastructure, environment variables, database schema, API contracts, and shared TypeScript interfaces. Business logic is intentionally not implemented here.

## Locked Foundation

- Python: 3.12
- Package manager: uv
- Database driver: asyncpg
- ORM: SQLAlchemy 2.0 async
- Migrations: Alembic
- Browser layer: browser-use 0.12.2
- Scheduler: APScheduler AsyncIOScheduler with CronTrigger
- Database: PostgreSQL
- Cache and locks: Redis
- Single-user v1 only

## Services

- `api`: FastAPI service shell
- `agent`: Browser automation service shell with `shm_size: 2gb`
- `postgres`: PostgreSQL database
- `redis`: Stop flag, locks, and scheduler coordination
- `backup`: weekly `pg_dump`, retaining 4 weeks

## Setup

1. Copy `.env.example` to `.env`.
2. Adjust secrets and user preferences.
3. Start services:

```powershell
docker compose up --build
```

## Foundation Boundary

This scaffold includes no business logic for sourcing jobs, scoring jobs, generating documents, answering screening questions, submitting applications, or browser actions.
