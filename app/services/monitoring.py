"""Background health monitoring with Telegram alerting to the operator.

The loop only observes signals visible from inside the backend container and
delivers alerts through the same proxy-aware bot the application already uses.
It cannot report a fully dead process or a total server outage; pair it with an
external dead-man-switch that pings ``/api/health/ready`` for that coverage.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from aiogram import Bot
from redis.asyncio import Redis
from sqlalchemy import text

from app.core.config import Settings
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

# The daily backup image writes gzipped SQL dumps; pre-deploy dumps use .dump.
BACKUP_GLOBS = ("*.sql.gz", "*.sql", "*.dump")


@dataclass(frozen=True)
class CheckResult:
    """Outcome of a single health check with a human-readable explanation."""

    healthy: bool
    detail: str


def newest_backup_age_hours(backup_dir: Path, *, now: float | None = None) -> float | None:
    """Return the age in hours of the most recent backup file, or None if absent."""
    reference = time.time() if now is None else now
    latest: float | None = None
    for pattern in BACKUP_GLOBS:
        for path in backup_dir.rglob(pattern):
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if latest is None or mtime > latest:
                latest = mtime
    if latest is None:
        return None
    return max(0.0, (reference - latest) / 3600.0)


def evaluate_backup(age_hours: float | None, max_age_hours: int) -> CheckResult:
    """Flag a missing or stale database backup."""
    if age_hours is None:
        return CheckResult(False, "no database backup found in the backup volume")
    if age_hours > max_age_hours:
        return CheckResult(False, f"latest backup is {age_hours:.1f}h old (limit {max_age_hours}h)")
    return CheckResult(True, f"latest backup is {age_hours:.1f}h old")


def evaluate_disk(percent_used: float, threshold_percent: int) -> CheckResult:
    """Flag a filesystem that is running out of room."""
    if percent_used >= threshold_percent:
        return CheckResult(False, f"disk {percent_used:.0f}% full (limit {threshold_percent}%)")
    return CheckResult(True, f"disk {percent_used:.0f}% full")


def transitions(current: dict[str, CheckResult], previous: dict[str, bool]) -> list[str]:
    """Produce alert lines only when a check flips between healthy and unhealthy."""
    messages: list[str] = []
    for name, result in current.items():
        was_healthy = previous.get(name, True)
        if result.healthy and not was_healthy:
            messages.append(f"✅ {name} recovered: {result.detail}")
        elif not result.healthy and was_healthy:
            messages.append(f"\U0001f534 {name}: {result.detail}")
    return messages


async def _check_database() -> CheckResult:
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - report any failure verbatim
        return CheckResult(False, f"PostgreSQL unavailable: {exc}")
    return CheckResult(True, "PostgreSQL reachable")


async def _check_redis(url: str) -> CheckResult:
    redis = Redis.from_url(url)
    try:
        await redis.ping()
    except Exception as exc:  # noqa: BLE001 - report any failure verbatim
        return CheckResult(False, f"Redis unavailable: {exc}")
    finally:
        await redis.aclose()
    return CheckResult(True, "Redis reachable")


async def _check_telegram(bot: Bot) -> CheckResult:
    try:
        await bot.get_me()
    except Exception as exc:  # noqa: BLE001 - report any failure verbatim
        return CheckResult(False, f"Telegram API unreachable: {exc}")
    return CheckResult(True, "Telegram API reachable")


def _check_backup_and_disk(settings: Settings) -> dict[str, CheckResult]:
    backup_dir = Path(settings.backup_dir)
    if not backup_dir.is_dir():
        return {}
    usage = shutil.disk_usage(backup_dir)
    percent = usage.used / usage.total * 100 if usage.total else 0.0
    return {
        "backup": evaluate_backup(
            newest_backup_age_hours(backup_dir), settings.backup_max_age_hours
        ),
        "disk": evaluate_disk(percent, settings.disk_alert_percent),
    }


async def collect_health(bot: Bot, settings: Settings) -> dict[str, CheckResult]:
    """Gather every observable health signal for one monitoring cycle."""
    results: dict[str, CheckResult] = {
        "database": await _check_database(),
        "redis": await _check_redis(settings.redis_url),
        "telegram": await _check_telegram(bot),
    }
    results.update(await asyncio.to_thread(_check_backup_and_disk, settings))
    return results


async def _send_alert(bot: Bot, settings: Settings, message: str) -> None:
    try:
        await bot.send_message(settings.effective_alert_id, message)
    except Exception:  # noqa: BLE001 - never let alerting crash the monitor
        logger.exception("Failed to deliver health alert: %s", message)


async def health_monitor_loop(bot: Bot, settings: Settings) -> None:
    """Alert the operator on Telegram whenever a health signal changes state."""
    previous: dict[str, bool] = {}
    while True:
        try:
            current = await collect_health(bot, settings)
            for message in transitions(current, previous):
                logger.warning("Health transition: %s", message)
                await _send_alert(bot, settings, message)
            previous = {name: result.healthy for name, result in current.items()}
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Health monitor iteration failed")
        await asyncio.sleep(settings.monitor_interval_seconds)
