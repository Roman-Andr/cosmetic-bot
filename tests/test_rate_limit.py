"""Unit tests for the pure rate-limit decision logic."""

from app.api.rate_limit import rate_limit_exceeded


def test_rate_limit_exceeded_allows_up_to_the_limit() -> None:
    assert rate_limit_exceeded(1, limit=20) is False
    assert rate_limit_exceeded(20, limit=20) is False


def test_rate_limit_exceeded_rejects_beyond_the_limit() -> None:
    assert rate_limit_exceeded(21, limit=20) is True
