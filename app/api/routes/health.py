"""Liveness and readiness probes for Docker and the reverse proxy."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from app.api.dependencies import SessionDependency

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live() -> dict[str, str]:
    """Return immediately when the ASGI process is alive."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(session: SessionDependency) -> dict[str, str]:
    """Return success only when PostgreSQL accepts a lightweight query."""
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable"
        ) from exc
    return {"status": "ok"}
