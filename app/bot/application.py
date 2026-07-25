"""Aiogram application factory and FastAPI webhook bridge."""

from __future__ import annotations

import hmac

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import Update
from fastapi import APIRouter, Header, HTTPException, Request, Response, status

from app.bot import handlers
from app.core.config import Settings


def create_bot(settings: Settings) -> Bot:
    """Create one Telegram client shared by webhook handlers and outbox delivery."""
    return Bot(token=settings.bot_token.get_secret_value())


def create_dispatcher(settings: Settings) -> Dispatcher:
    """Use Redis rather than in-memory state so sale drafts survive a restart."""
    dispatcher = Dispatcher(storage=RedisStorage.from_url(settings.redis_url))
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
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=False,
    )
