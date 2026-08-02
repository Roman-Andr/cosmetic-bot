"""Redis-backed fixed-window throttling for abuse-prone admin endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from redis.asyncio import Redis

from app.api.dependencies import SalesAdminDependency
from app.db.redis import get_redis

RedisDependency = Annotated[Redis, Depends(get_redis)]


def rate_limit_exceeded(count: int, limit: int) -> bool:
    """Decide whether the Nth call within the current fixed window must be rejected."""
    return count > limit


class RateLimiter:
    """Cap how many times one admin may hit a scope within a rolling fixed window.

    Buyer codes are six digits and are only ever checked by HMAC digest (see
    ``LoyaltyService.record_purchase``/``lookup_buyer``), so without a guard here an
    authenticated-but-malicious sales account could script a brute-force search across
    a code's one-hour validity window instead of guessing at human speed.
    """

    def __init__(self, *, limit: int, window_seconds: int, scope: str) -> None:
        self._limit = limit
        self._window_seconds = window_seconds
        self._scope = scope

    async def __call__(self, redis: RedisDependency, admin: SalesAdminDependency) -> None:
        key = f"ratelimit:{self._scope}:{admin.telegram_user_id}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, self._window_seconds)
        if rate_limit_exceeded(count, self._limit):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many buyer code attempts, try again later",
            )


# Shared across preview/lookup/record so switching endpoints cannot bypass the cap.
buyer_code_rate_limit = RateLimiter(limit=20, window_seconds=60, scope="buyer-code")
BuyerCodeRateLimitDependency = Annotated[None, Depends(buyer_code_rate_limit)]
