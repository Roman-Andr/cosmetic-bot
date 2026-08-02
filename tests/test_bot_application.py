"""Telegram client construction tests."""

from collections.abc import Iterator

import pytest
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession

from app.core.config import Settings


@pytest.fixture
def settings_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Provide the required settings without reading a developer .env file."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("BOT_TOKEN", "123456:test-token")
    monkeypatch.setenv("OWNER_TELEGRAM_ID", "1")
    monkeypatch.setenv("WEBHOOK_SECRET", "test-webhook-secret")
    monkeypatch.setenv("LOYALTY_CODE_PEPPER", "test-loyalty-pepper")
    yield


@pytest.mark.usefixtures("settings_env")
async def test_create_bot_uses_configured_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Route every aiogram request through the production SOCKS5 sidecar."""
    from app.bot.application import create_bot

    monkeypatch.setenv("TELEGRAM_PROXY_URL", "socks5://hysteria:1080")

    bot = create_bot(Settings(_env_file=None))

    assert isinstance(bot, Bot)
    assert isinstance(bot.session, AiohttpSession)
    assert bot.session._proxy == "socks5://hysteria:1080"
    await bot.session.close()


@pytest.mark.usefixtures("settings_env")
async def test_create_bot_keeps_direct_session_without_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep local development usable when no proxy is configured."""
    from app.bot.application import create_bot

    monkeypatch.delenv("TELEGRAM_PROXY_URL", raising=False)

    bot = create_bot(Settings(_env_file=None))

    assert isinstance(bot.session, AiohttpSession)
    assert bot.session._proxy is None
    await bot.session.close()
