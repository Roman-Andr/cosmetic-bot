"""Structural regression tests for the Telegram router composition root."""

from collections.abc import Iterator

import pytest
from aiogram import Router

from app.core.config import get_settings


@pytest.fixture
def bot_router(monkeypatch: pytest.MonkeyPatch) -> Iterator[Router]:
    """Load the router tree with isolated, non-secret test settings."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("BOT_TOKEN", "test-token")
    monkeypatch.setenv("OWNER_TELEGRAM_ID", "1")
    monkeypatch.setenv("WEBHOOK_SECRET", "test-webhook-secret")
    monkeypatch.setenv("LOYALTY_CODE_PEPPER", "test-loyalty-pepper")
    get_settings.cache_clear()

    from app.bot.handlers import router

    yield router
    get_settings.cache_clear()


def test_domain_routers_keep_intentional_order(bot_router: Router) -> None:
    """Keep stateful workflows ahead of the catch-all support router."""
    assert [router.name for router in bot_router.sub_routers] == [
        "customer-workflows",
        "sales-workflows",
        "owner-workflows",
        "support-workflows",
    ]


def test_domain_routers_register_all_existing_handlers(bot_router: Router) -> None:
    """Guard against dropping handlers during future module moves."""
    handler_counts = {
        router.name: {
            update_type: len(observer.handlers)
            for update_type, observer in router.observers.items()
            if observer.handlers
        }
        for router in bot_router.sub_routers
    }

    assert handler_counts == {
        "customer-workflows": {"message": 7},
        "sales-workflows": {"message": 4, "callback_query": 4},
        "owner-workflows": {"message": 10, "callback_query": 3},
        "support-workflows": {"message": 2, "callback_query": 4},
    }
    assert bot_router.resolve_used_update_types() == ["callback_query", "message"]
