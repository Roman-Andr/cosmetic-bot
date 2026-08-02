"""Shared async Redis client reused by rate limiting and health checks."""

from __future__ import annotations

from functools import lru_cache

from redis.asyncio import Redis

from app.core.config import get_settings


@lru_cache
def get_redis_client() -> Redis:
    """Build one Redis client reused by FastAPI dependencies for the process lifetime."""
    return Redis.from_url(get_settings().redis_url)


async def get_redis() -> Redis:
    """FastAPI dependency exposing the shared Redis client."""
    return get_redis_client()
