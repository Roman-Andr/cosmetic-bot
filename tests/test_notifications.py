"""Outbox delivery chooses between a plain message and a photo with caption."""

from collections.abc import Iterator
from typing import Any

import pytest

from app.models import NotificationOutbox


@pytest.fixture
def settings_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The delivery module opens the session factory, which needs the required settings."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("BOT_TOKEN", "123456:test-token")
    monkeypatch.setenv("OWNER_TELEGRAM_ID", "1")
    monkeypatch.setenv("WEBHOOK_SECRET", "test-webhook-secret")
    monkeypatch.setenv("LOYALTY_CODE_PEPPER", "test-loyalty-pepper")
    yield


class RecordingBot:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.calls.append(("message", {"chat_id": chat_id, "text": text}))

    async def send_photo(self, chat_id: int, *, photo: str, caption: str) -> None:
        self.calls.append(("photo", {"chat_id": chat_id, "photo": photo, "caption": caption}))


@pytest.mark.usefixtures("settings_env")
async def test_campaign_notification_is_sent_as_photo_with_caption() -> None:
    from app.bot.notifications import deliver

    bot = RecordingBot()
    await deliver(bot, NotificationOutbox(chat_id=7, body="Акция", photo_file_id="file-1"))  # type: ignore[arg-type]
    await deliver(bot, NotificationOutbox(chat_id=8, body="Начислено"))  # type: ignore[arg-type]

    assert bot.calls == [
        ("photo", {"chat_id": 7, "photo": "file-1", "caption": "Акция"}),
        ("message", {"chat_id": 8, "text": "Начислено"}),
    ]
