from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from urllib.parse import urlencode

import pytest
from pydantic import SecretStr

from app.services.telegram_auth import TelegramAuthError, validate_init_data


def signed_init_data(token: str) -> str:
    """Build a Telegram-compatible signed init-data sample for verification tests."""
    fields = {
        "auth_date": str(int(datetime.now(UTC).timestamp())),
        "query_id": "AAEAAAE",
        "user": json.dumps({"id": 12345, "first_name": "Анна", "username": "anna"}),
    }
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


def test_validates_signed_telegram_init_data() -> None:
    init_data = signed_init_data("test-token")
    identity = validate_init_data(init_data, SecretStr("test-token"))
    assert identity.telegram_user_id == 12345
    assert identity.username == "anna"


def test_rejects_tampered_telegram_init_data() -> None:
    with pytest.raises(TelegramAuthError, match="signature"):
        validate_init_data(
            signed_init_data("test-token").replace("12345", "99999"),
            SecretStr("test-token"),
        )
