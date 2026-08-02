"""ASGI entry point for the Mini App API and Telegram webhook application."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import admin, health, loyalty
from app.bot.application import (
    configure_webhook,
    create_bot,
    create_dispatcher,
    create_webhook_router,
)
from app.bot.notifications import notification_delivery_loop, stop_notification_task
from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.services.bootstrap import seed_defaults
from app.services.catalog import CatalogService, CatalogSyncError

logger = logging.getLogger(__name__)
settings = get_settings()
bot = create_bot(settings)
dispatcher = create_dispatcher(settings)


async def catalogue_sync_loop() -> None:
    """Synchronize the optional Google Sheets catalogue on a controlled interval."""
    if not settings.google_sheets_credentials_file:
        logger.warning("Google Sheets synchronization is disabled: no credentials file configured")
        return

    service = CatalogService(settings)
    while True:
        try:
            async with SessionLocal() as session:
                count = await service.sync(session)
                logger.info("Synchronized %s catalogue products", count)
        except CatalogSyncError:
            logger.exception("Catalogue synchronization failed")
        except Exception:
            logger.exception("Unexpected catalogue synchronization failure")
        await asyncio.sleep(settings.product_sync_interval_seconds)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Seed first-run settings and cleanly stop background resources."""
    async with SessionLocal() as session:
        await seed_defaults(session, settings)
    sync_task = asyncio.create_task(catalogue_sync_loop(), name="catalogue-sync")
    polling_task: asyncio.Task[None] | None = None
    if settings.telegram_mode == "webhook":
        await configure_webhook(bot, settings)
    else:
        await bot.delete_webhook(drop_pending_updates=False)
        polling_task = asyncio.create_task(
            dispatcher.start_polling(
                bot,
                allowed_updates=["message", "callback_query"],
                handle_signals=False,
                close_bot_session=False,
            ),
            name="telegram-polling",
        )
    notification_task = asyncio.create_task(
        notification_delivery_loop(bot), name="notification-outbox"
    )
    try:
        yield
    finally:
        await stop_notification_task(notification_task)
        if polling_task is not None:
            polling_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await polling_task
        sync_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await sync_task
        await dispatcher.storage.close()
        await bot.session.close()
        await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    docs_url="/api/docs" if settings.app_env != "production" else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if settings.app_env != "production" else None,
    lifespan=lifespan,
)
app.include_router(health.router, prefix="/api")
app.include_router(loyalty.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(create_webhook_router(bot, dispatcher, settings), prefix="/api")


def main() -> None:
    """Run the production ASGI server via the package script."""
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, proxy_headers=True)
