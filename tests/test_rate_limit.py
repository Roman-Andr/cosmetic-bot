"""Unit tests for the pure rate-limit decision logic."""

from collections.abc import Callable, Iterator

import pytest

from app.core.config import get_settings


@pytest.fixture
def rate_limit_exceeded(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., bool]]:
    """Import the decision function only after the settings its module needs exist.

    ``app.api.rate_limit`` type-annotates a dependency with ``SalesAdminDependency``,
    which transitively imports ``app.db.session`` and builds ``Settings()`` at import
    time - so, same as ``tests/test_bot_routing.py``, provide non-secret test values
    instead of relying on a developer's local .env file.
    """
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("BOT_TOKEN", "test-token")
    monkeypatch.setenv("OWNER_TELEGRAM_ID", "1")
    monkeypatch.setenv("WEBHOOK_SECRET", "test-webhook-secret")
    monkeypatch.setenv("LOYALTY_CODE_PEPPER", "test-loyalty-pepper")
    get_settings.cache_clear()

    from app.api.rate_limit import rate_limit_exceeded as func

    yield func
    get_settings.cache_clear()


def test_rate_limit_exceeded_allows_up_to_the_limit(
    rate_limit_exceeded: Callable[..., bool],
) -> None:
    assert rate_limit_exceeded(1, limit=20) is False
    assert rate_limit_exceeded(20, limit=20) is False


def test_rate_limit_exceeded_rejects_beyond_the_limit(
    rate_limit_exceeded: Callable[..., bool],
) -> None:
    assert rate_limit_exceeded(21, limit=20) is True
