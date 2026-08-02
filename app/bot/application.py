"""Aiogram application factory and FastAPI webhook bridge."""

from __future__ import annotations

import asyncio
import hmac
import logging
from datetime import timedelta

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import Update
from fastapi import APIRouter, Header, HTTPException, Request, Response, status

from app.bot import handlers
from app.core.config import Settings

logger = logging.getLogger(__name__)

_TELEGRAM_ALLOWED_UPDATES = ["message", "callback_query"]
_TELEGRAM_RETRY_SECONDS = 30


def create_bot(settings: Settings) -> Bot:
    """Create one Telegram client shared by webhook handlers and outbox delivery."""
    session = None
    if settings.telegram_proxy_url is not None:
        session = AiohttpSession(proxy=settings.telegram_proxy_url.get_secret_value())
    return Bot(token=settings.bot_token.get_secret_value(), session=session)


def create_dispatcher(settings: Settings) -> Dispatcher:
    """Use Redis rather than in-memory state so sale drafts survive a restart."""
    ttl = timedelta(seconds=settings.fsm_ttl_seconds) if settings.fsm_ttl_seconds > 0 else None
    dispatcher = Dispatcher(
        storage=RedisStorage.from_url(settings.redis_url, state_ttl=ttl, data_ttl=ttl)
    )
    dispatcher.include_router(handlers.router)
    return dispatcher


def create_webhook_router(bot: Bot, dispatcher: Dispatcher, settings: Settings) -> APIRouter:
    """Expose a secret-protected route for Telegram updates."""
    router = APIRouter(prefix="/telegram", tags=["telegram"])

    @router.post("/webhook", status_code=status.HTTP_204_NO_CONTENT)
    async def telegram_webhook(
        request: Request,
        x_telegram_bot_api_secret_token: str | None = Header(default=None),
    ) -> Response:
        """Validate Telegram's header token before feeding an update to aiogram."""
        expected_secret = settings.webhook_secret.get_secret_value()
        if not x_telegram_bot_api_secret_token or not hmac.compare_digest(
            x_telegram_bot_api_secret_token,
            expected_secret,
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook secret"
            )
        update = Update.model_validate(await request.json(), context={"bot": bot})
        await dispatcher.feed_update(bot, update)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router


async def configure_webhook(bot: Bot, settings: Settings) -> None:
    """Point Telegram to the HTTPS application endpoint with a secret token."""
    await bot.set_webhook(
        url=settings.webhook_url,
        secret_token=settings.webhook_secret.get_secret_value(),
        allowed_updates=_TELEGRAM_ALLOWED_UPDATES,
        drop_pending_updates=False,
    )


async def run_telegram(bot: Bot, dispatcher: Dispatcher, settings: Settings) -> None:
    """Connect the bot to Telegram without blocking API startup on transient outages.

    A dead upstream VPN or Telegram block must degrade only the bot, never the Mini
    App API, so connection failures are retried in the background instead of raising
    out of the ASGI lifespan and forcing a container restart loop.
    """
    if settings.telegram_mode == "webhook":
        while True:
            try:
                await configure_webhook(bot, settings)
                return
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Failed to configure Telegram webhook; retrying")
                await asyncio.sleep(_TELEGRAM_RETRY_SECONDS)

    while True:
        try:
            await bot.delete_webhook(drop_pending_updates=False)
            break
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Failed to drop webhook before polling; retrying")
            await asyncio.sleep(_TELEGRAM_RETRY_SECONDS)

    await dispatcher.start_polling(
        bot,
        allowed_updates=_TELEGRAM_ALLOWED_UPDATES,
        handle_signals=False,
        close_bot_session=False,
    )
