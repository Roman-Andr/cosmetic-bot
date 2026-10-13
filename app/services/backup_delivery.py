"""Off-site copy of the daily database dump, delivered as a Telegram document.

Every dump otherwise lives on the server's single disk next to the database. This loop
sends each new daily dump once to ``BACKUP_TELEGRAM_ID`` through the same proxy-aware bot
the application already uses. The name of the last delivered file is kept in Redis, so
restarts do not resend it and a failed upload is retried on the next cycle.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile
from redis.asyncio import Redis

from app.core.config import Settings

logger = logging.getLogger(__name__)

LAST_SENT_KEY = "backup-delivery:last-sent"
# Bot API refuses uploads above 50 MB.
TELEGRAM_UPLOAD_LIMIT_BYTES = 50 * 1024 * 1024
CHECK_INTERVAL_SECONDS = 1800


def newest_daily_backup(backup_dir: Path) -> Path | None:
    """Return the newest dated daily dump, skipping the ``*-latest`` symlink."""
    daily = backup_dir / "daily"
    if not daily.is_dir():
        return None
    candidates = [
        path
        for path in daily.glob("*.sql.gz")
        if path.is_file() and not path.is_symlink() and not path.name.endswith("-latest.sql.gz")
    ]
    # File names embed the date (cosmetic-YYYYMMDD.sql.gz), so the name order is the age order.
    return max(candidates, key=lambda path: path.name, default=None)


def backup_caption(path: Path) -> str:
    """Describe a dump in the message that carries it."""
    size_kb = path.stat().st_size / 1024
    return f"\U0001f4be Бэкап базы: {path.name} ({size_kb:.0f} КБ)"


async def deliver_new_backup(bot: Bot, redis: Redis, settings: Settings) -> str | None:
    """Send the newest daily dump if it has not been delivered yet; return its name."""
    if settings.backup_telegram_id is None:
        return None
    path = await asyncio.to_thread(newest_daily_backup, Path(settings.backup_dir))
    if path is None:
        return None
    last_sent = await redis.get(LAST_SENT_KEY)
    if isinstance(last_sent, bytes):
        last_sent = last_sent.decode()
    if last_sent == path.name:
        return None

    if path.stat().st_size > TELEGRAM_UPLOAD_LIMIT_BYTES:
        await bot.send_message(
            settings.backup_telegram_id,
            f"⚠️ Бэкап {path.name} больше 50 МБ, Telegram его не примет. "
            "Скопируйте его с сервера вручную.",
        )
    else:
        await bot.send_document(
            settings.backup_telegram_id,
            FSInputFile(path),
            caption=backup_caption(path),
            disable_notification=True,
        )
    await redis.set(LAST_SENT_KEY, path.name)
    logger.info("Delivered database backup %s to Telegram", path.name)
    return path.name


async def backup_delivery_loop(bot: Bot, redis: Redis, settings: Settings) -> None:
    """Send each new daily dump to the configured Telegram chat."""
    if settings.backup_telegram_id is None:
        logger.info("Telegram backup delivery is disabled: BACKUP_TELEGRAM_ID is not set")
        return
    while True:
        try:
            await deliver_new_backup(bot, redis, settings)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Telegram backup delivery failed; retrying next cycle")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
