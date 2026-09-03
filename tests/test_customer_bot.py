"""Customer-facing Telegram command tests."""

from collections.abc import Iterator
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Message, User

from app.core.config import get_settings


@pytest.fixture
def customer_router(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    """Load customer handlers only after configuring their required settings."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("BOT_TOKEN", "test-token")
    monkeypatch.setenv("OWNER_TELEGRAM_ID", "1")
    monkeypatch.setenv("WEBHOOK_SECRET", "test-webhook-secret")
    monkeypatch.setenv("LOYALTY_CODE_PEPPER", "test-loyalty-pepper")
    get_settings.cache_clear()

    from app.bot.routers import customer

    yield customer
    get_settings.cache_clear()


async def test_show_telegram_id_returns_copyable_sender_id(
    customer_router: ModuleType,
) -> None:
    """Let any Telegram user retrieve the ID needed for sales access."""
    message = MagicMock(spec=Message)
    message.from_user = User(id=123456789, is_bot=False, first_name="Sales")
    message.answer = AsyncMock()

    await customer_router.show_telegram_id(message)

    message.answer.assert_awaited_once_with(
        "Ваш Telegram ID: <code>123456789</code>",
        parse_mode="HTML",
    )


async def test_show_telegram_id_ignores_messages_without_sender(
    customer_router: ModuleType,
) -> None:
    """Handle synthetic channel messages that do not carry a Telegram user."""
    message = MagicMock(spec=Message)
    message.from_user = None
    message.answer = AsyncMock()

    await customer_router.show_telegram_id(message)

    message.answer.assert_not_awaited()
