"""Customer-facing Telegram command tests."""

from unittest.mock import AsyncMock, MagicMock

from aiogram.types import Message, User

from app.bot.routers.customer import show_telegram_id


async def test_show_telegram_id_returns_copyable_sender_id() -> None:
    """Let any Telegram user retrieve the ID needed for sales access."""
    message = MagicMock(spec=Message)
    message.from_user = User(id=123456789, is_bot=False, first_name="Sales")
    message.answer = AsyncMock()

    await show_telegram_id(message)

    message.answer.assert_awaited_once_with(
        "Ваш Telegram ID: <code>123456789</code>\n"
        "Отправьте его главному администратору для выдачи доступа.",
        parse_mode="HTML",
    )


async def test_show_telegram_id_ignores_messages_without_sender() -> None:
    """Handle synthetic channel messages that do not carry a Telegram user."""
    message = MagicMock(spec=Message)
    message.from_user = None
    message.answer = AsyncMock()

    await show_telegram_id(message)

    message.answer.assert_not_awaited()
