"""Transactional outbox delivery to Telegram."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime

from aiogram import Bot
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import NotificationOutbox

logger = logging.getLogger(__name__)


async def notification_delivery_loop(bot: Bot) -> None:
    """Deliver unsent notifications with bounded retries and row locks."""
    while True:
        try:
            async with SessionLocal() as session:
                notifications = list(
                    (
                        await session.scalars(
                            select(NotificationOutbox)
                            .where(
                                NotificationOutbox.sent_at.is_(None),
                                NotificationOutbox.attempts < 10,
                            )
                            .order_by(NotificationOutbox.created_at)
                            .limit(50)
                            .with_for_update(skip_locked=True)
                        )
                    ).all()
                )
                for notification in notifications:
                    try:
                        await bot.send_message(notification.chat_id, notification.body)
                    except Exception as exc:
                        notification.attempts += 1
                        notification.last_error = str(exc)[:1000]
                        logger.warning("Notification %s delivery failed: %s", notification.id, exc)
                    else:
                        notification.sent_at = datetime.now(UTC)
                        notification.attempts += 1
                        notification.last_error = None
                if notifications:
                    await session.commit()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Notification outbox delivery loop failed")
        await asyncio.sleep(10)


async def stop_notification_task(task: asyncio.Task[None]) -> None:
    """Cancel notification delivery without leaking an asyncio warning."""
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
