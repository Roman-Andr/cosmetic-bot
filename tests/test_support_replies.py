"""Owner replies are routed to customers only from the main owner's chat."""

from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.config import get_settings
from app.models import AdminRole, SupportDialogStatus

SECOND_OWNER_ID = 769517888
CUSTOMER_ID = 4242
FORWARDED_MESSAGE_ID = 150


@pytest.fixture
def support(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """Load the support router with isolated, non-secret test settings."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("BOT_TOKEN", "test-token")
    monkeypatch.setenv("OWNER_TELEGRAM_ID", "1")
    monkeypatch.setenv("WEBHOOK_SECRET", "test-webhook-secret")
    monkeypatch.setenv("LOYALTY_CODE_PEPPER", "test-loyalty-pepper")
    get_settings.cache_clear()

    from app.bot.routers import support as module

    async def every_caller_is_owner(_: int) -> AdminRole:
        return AdminRole.OWNER

    monkeypatch.setattr(module, "get_admin_role", every_caller_is_owner)
    yield module
    get_settings.cache_clear()


class RecordingBot:
    def __init__(self) -> None:
        self.copies: list[dict[str, int]] = []

    async def copy_message(self, *, chat_id: int, from_chat_id: int, message_id: int) -> None:
        self.copies.append(
            {"chat_id": chat_id, "from_chat_id": from_chat_id, "message_id": message_id}
        )


class FakeSession:
    """Answers the forward lookup as if message 150 were a forwarded customer message."""

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def scalar(self, _: object) -> SimpleNamespace:
        return SimpleNamespace(dialog_id="dialog")

    async def get(self, _: object, __: object) -> SimpleNamespace:
        return SimpleNamespace(status=SupportDialogStatus.OPEN, customer_telegram_id=CUSTOMER_ID)


def reply(*, chat_id: int, user_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        chat=SimpleNamespace(id=chat_id),
        from_user=SimpleNamespace(id=user_id),
        message_id=900,
        reply_to_message=SimpleNamespace(message_id=FORWARDED_MESSAGE_ID),
    )


async def test_second_owner_reply_never_reaches_a_customer(
    support: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_database() -> None:
        raise AssertionError("a reply outside the owner chat must not query support forwards")

    monkeypatch.setattr(support, "SessionLocal", no_database)
    bot = RecordingBot()

    await support.owner_reply_to_support(
        reply(chat_id=SECOND_OWNER_ID, user_id=SECOND_OWNER_ID), bot
    )

    assert bot.copies == []


async def test_main_owner_reply_is_copied_to_the_customer(
    support: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(support, "SessionLocal", FakeSession)
    owner_id = support.settings.owner_telegram_id
    bot = RecordingBot()

    await support.owner_reply_to_support(reply(chat_id=owner_id, user_id=owner_id), bot)

    assert bot.copies == [{"chat_id": CUSTOMER_ID, "from_chat_id": owner_id, "message_id": 900}]
