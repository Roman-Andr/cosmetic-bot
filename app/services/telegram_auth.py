"""Server-side validation of Telegram Mini App initial data."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl

from pydantic import SecretStr


class TelegramAuthError(ValueError):
    """Raised when Mini App data cannot be trusted."""


@dataclass(frozen=True)
class TelegramIdentity:
    """Authenticated user identity extracted from verified Telegram init data."""

    telegram_user_id: int
    username: str | None
    first_name: str
    last_name: str | None


def validate_init_data(
    init_data: str,
    bot_token: SecretStr,
    *,
    max_age: timedelta = timedelta(hours=24),
) -> TelegramIdentity:
    """Validate Telegram HMAC and freshness before using user data from the client."""
    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    supplied_hash = parsed.pop("hash", None)
    if not supplied_hash:
        raise TelegramAuthError("Telegram init data does not include a hash")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(parsed.items()))
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.get_secret_value().encode(),
        hashlib.sha256,
    ).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, supplied_hash):
        raise TelegramAuthError("Telegram init data signature is invalid")

    try:
        auth_date = datetime.fromtimestamp(int(parsed["auth_date"]), tz=UTC)
        telegram_user = json.loads(parsed["user"])
        user_id = int(telegram_user["id"])
        first_name = str(telegram_user["first_name"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise TelegramAuthError("Telegram init data is incomplete") from exc

    now = datetime.now(UTC)
    if auth_date > now + timedelta(minutes=5) or now - auth_date > max_age:
        raise TelegramAuthError("Telegram init data has expired")

    username = telegram_user.get("username")
    last_name = telegram_user.get("last_name")
    return TelegramIdentity(
        telegram_user_id=user_id,
        username=str(username) if username else None,
        first_name=first_name,
        last_name=str(last_name) if last_name else None,
    )
