"""Transactional outbox delivery to Telegram."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import NotificationOutbox

logger = logging.getLogger(__name__)

MAX_DELIVERY_ATTEMPTS = 10
BATCH_SIZE = 50
IDLE_SECONDS = 10
# Telegram allows roughly 30 messages per second; stay well below it during broadcasts.
SEND_INTERVAL_SECONDS = 0.05


async def deliver(bot: Bot, notification: NotificationOutbox) -> None:
    """Send one queued notification as a photo with caption or as plain text."""
    if notification.photo_file_id:
        await bot.send_photo(
            notification.chat_id,
            photo=notification.photo_file_id,
            caption=notification.body,
        )
    else:
        await bot.send_message(notification.chat_id, notification.body)


async def notification_delivery_loop(bot: Bot) -> None:
    """Deliver unsent notifications with bounded retries and row locks."""
    while True:
        batch_size = 0
        try:
            async with SessionLocal() as session:
                notifications = list(
                    (
                        await session.scalars(
                            select(NotificationOutbox)
                            .where(
                                NotificationOutbox.sent_at.is_(None),
                                NotificationOutbox.attempts < MAX_DELIVERY_ATTEMPTS,
                            )
                            .order_by(NotificationOutbox.created_at)
                            .limit(BATCH_SIZE)
                            .with_for_update(skip_locked=True)
                        )
                    ).all()
                )
                batch_size = len(notifications)
                for notification in notifications:
                    try:
                        await deliver(bot, notification)
                    except TelegramRetryAfter as exc:
                        # Flood control is not the recipient's fault: wait and keep the attempt.
                        notification.last_error = str(exc)[:1000]
                        logger.warning("Telegram flood control, retrying in %ss", exc.retry_after)
                        await asyncio.sleep(exc.retry_after)
                        break
                    except TelegramForbiddenError as exc:
                        # The customer blocked the bot; retrying cannot succeed.
                        notification.attempts = MAX_DELIVERY_ATTEMPTS
                        notification.last_error = str(exc)[:1000]
                        logger.info("Notification %s recipient blocked the bot", notification.id)
                    except Exception as exc:
                        notification.attempts += 1
                        notification.last_error = str(exc)[:1000]
                        logger.warning("Notification %s delivery failed: %s", notification.id, exc)
                    else:
                        notification.sent_at = datetime.now(UTC)
                        notification.attempts += 1
                        notification.last_error = None
                    await asyncio.sleep(SEND_INTERVAL_SECONDS)
                if notifications:
                    await session.commit()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Notification outbox delivery loop failed")
            batch_size = 0
        # A full batch means a broadcast is draining; continue without the idle pause.
        if batch_size < BATCH_SIZE:
            await asyncio.sleep(IDLE_SECONDS)


async def stop_notification_task(task: asyncio.Task[None]) -> None:
    """Cancel notification delivery without leaking an asyncio warning."""
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
