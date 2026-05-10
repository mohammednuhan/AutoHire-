from __future__ import annotations

import gzip
import logging
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from notifications.telegram import send_health_alert
from storage import data_dir

logger = logging.getLogger("autohire.maintenance.backup")

_backup_scheduler: AsyncIOScheduler | None = None


async def run_weekly_backup() -> Path | None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        await send_health_alert("Backup", "DATABASE_URL is not configured")
        return None

    backup_dir = data_dir() / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    sql_path = backup_dir / f"autohire_{stamp}.sql"
    gz_path = backup_dir / f"{sql_path.name}.gz"

    dump_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    with sql_path.open("wb") as output:
        subprocess.run(["pg_dump", dump_url], stdout=output, check=True)

    with sql_path.open("rb") as source, gzip.open(gz_path, "wb") as target:
        shutil.copyfileobj(source, target)
    sql_path.unlink(missing_ok=True)

    if gz_path.stat().st_size <= 10 * 1024:
        await send_health_alert("Backup", f"Backup file looks too small: {gz_path}")

    backups = sorted(backup_dir.glob("autohire_*.sql.gz"), key=lambda path: path.stat().st_mtime, reverse=True)
    for old_backup in backups[4:]:
        old_backup.unlink(missing_ok=True)

    logger.info("backup_completed", extra={"path": str(gz_path), "size": gz_path.stat().st_size})
    return gz_path


def start_backup_scheduler() -> None:
    global _backup_scheduler
    if _backup_scheduler and _backup_scheduler.running:
        return
    timezone_name = os.getenv("USER_TIMEZONE", "Asia/Kolkata")
    _backup_scheduler = AsyncIOScheduler(timezone=timezone_name)
    _backup_scheduler.add_job(
        run_weekly_backup,
        trigger=CronTrigger(day_of_week="sun", hour=2, minute=0, timezone=timezone_name),
        id="weekly_backup",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    _backup_scheduler.start()


async def stop_backup_scheduler() -> None:
    global _backup_scheduler
    if _backup_scheduler and _backup_scheduler.running:
        _backup_scheduler.shutdown(wait=False)
    _backup_scheduler = None
