"""Tests for sending daily database dumps to Telegram."""

from pathlib import Path
from typing import Any, cast

import pytest
from aiogram import Bot
from redis.asyncio import Redis

from app.core.config import Settings
from app.services.backup_delivery import (
    LAST_SENT_KEY,
    TELEGRAM_UPLOAD_LIMIT_BYTES,
    deliver_new_backup,
    newest_daily_backup,
)


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.values.get(key)

    async def set(self, key: str, value: str) -> None:
        self.values[key] = value.encode()


class FakeBot:
    def __init__(self, *, fail: bool = False) -> None:
        self.documents: list[tuple[int, str, str]] = []
        self.messages: list[tuple[int, str]] = []
        self.fail = fail

    async def send_document(self, chat_id: int, document: Any, **kwargs: Any) -> None:
        if self.fail:
            raise RuntimeError("Telegram unreachable")
        self.documents.append((chat_id, Path(document.path).name, kwargs["caption"]))

    async def send_message(self, chat_id: int, text: str) -> None:
        self.messages.append((chat_id, text))


def make_settings(backup_dir: Path, backup_telegram_id: int | None = 42) -> Settings:
    return Settings.model_construct(
        backup_dir=str(backup_dir), backup_telegram_id=backup_telegram_id
    )


def write_dump(backup_dir: Path, name: str, size: int = 2048) -> Path:
    daily = backup_dir / "daily"
    daily.mkdir(parents=True, exist_ok=True)
    path = daily / name
    path.write_bytes(b"x" * size)
    return path


async def deliver(bot: FakeBot, redis: FakeRedis, settings: Settings) -> str | None:
    return await deliver_new_backup(cast(Bot, bot), cast(Redis, redis), settings)


def test_newest_daily_backup_picks_latest_date_and_skips_latest_link(tmp_path: Path) -> None:
    assert newest_daily_backup(tmp_path) is None

    write_dump(tmp_path, "cosmetic-20261012.sql.gz")
    newest = write_dump(tmp_path, "cosmetic-20261013.sql.gz")
    write_dump(tmp_path, "cosmetic-20261011.sql.gz")
    (tmp_path / "daily" / "cosmetic-latest.sql.gz").symlink_to(newest.name)

    assert newest_daily_backup(tmp_path) == newest


async def test_new_backup_is_sent_once(tmp_path: Path) -> None:
    write_dump(tmp_path, "cosmetic-20261013.sql.gz")
    bot, redis = FakeBot(), FakeRedis()
    settings = make_settings(tmp_path)

    assert await deliver(bot, redis, settings) == "cosmetic-20261013.sql.gz"
    assert await deliver(bot, redis, settings) is None

    assert len(bot.documents) == 1
    chat_id, name, caption = bot.documents[0]
    assert (chat_id, name) == (42, "cosmetic-20261013.sql.gz")
    assert "cosmetic-20261013.sql.gz" in caption
    assert redis.values[LAST_SENT_KEY] == b"cosmetic-20261013.sql.gz"


async def test_next_day_backup_is_sent_after_previous(tmp_path: Path) -> None:
    write_dump(tmp_path, "cosmetic-20261013.sql.gz")
    bot, redis = FakeBot(), FakeRedis()
    settings = make_settings(tmp_path)
    await deliver(bot, redis, settings)

    write_dump(tmp_path, "cosmetic-20261014.sql.gz")

    assert await deliver(bot, redis, settings) == "cosmetic-20261014.sql.gz"
    assert [name for _, name, _ in bot.documents] == [
        "cosmetic-20261013.sql.gz",
        "cosmetic-20261014.sql.gz",
    ]


async def test_failed_upload_is_retried_next_cycle(tmp_path: Path) -> None:
    write_dump(tmp_path, "cosmetic-20261013.sql.gz")
    redis = FakeRedis()
    settings = make_settings(tmp_path)

    with pytest.raises(RuntimeError):
        await deliver(FakeBot(fail=True), redis, settings)
    assert LAST_SENT_KEY not in redis.values

    bot = FakeBot()
    assert await deliver(bot, redis, settings) == "cosmetic-20261013.sql.gz"
    assert len(bot.documents) == 1


async def test_delivery_is_disabled_without_recipient(tmp_path: Path) -> None:
    write_dump(tmp_path, "cosmetic-20261013.sql.gz")
    bot, redis = FakeBot(), FakeRedis()

    assert await deliver(bot, redis, make_settings(tmp_path, backup_telegram_id=None)) is None
    assert bot.documents == []
    assert redis.values == {}


async def test_oversized_backup_sends_warning_instead_of_file(tmp_path: Path) -> None:
    write_dump(tmp_path, "cosmetic-20261013.sql.gz", size=TELEGRAM_UPLOAD_LIMIT_BYTES + 1)
    bot, redis = FakeBot(), FakeRedis()

    assert await deliver(bot, redis, make_settings(tmp_path)) == "cosmetic-20261013.sql.gz"
    assert bot.documents == []
    assert len(bot.messages) == 1
    assert "50 МБ" in bot.messages[0][1]
