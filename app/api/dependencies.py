"""FastAPI dependencies for Telegram authentication and role checks."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models import AdminRole, AdminUser, Customer
from app.services.telegram_auth import TelegramAuthError, TelegramIdentity, validate_init_data

SettingsDependency = Annotated[Settings, Depends(get_settings)]
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


async def get_telegram_identity(
    settings: SettingsDependency,
    x_telegram_init_data: Annotated[str | None, Header()] = None,
) -> TelegramIdentity:
    """Authenticate the HTTP caller using the header sent by the Mini App."""
    if not x_telegram_init_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Telegram init data"
        )
    try:
        return validate_init_data(x_telegram_init_data, settings.bot_token)
    except TelegramAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


IdentityDependency = Annotated[TelegramIdentity, Depends(get_telegram_identity)]


async def get_current_customer(
    session: SessionDependency,
    identity: IdentityDependency,
) -> Customer:
    """Resolve an authenticated Telegram user to a loyalty customer."""
    customer = await session.scalar(
        select(Customer).where(Customer.telegram_user_id == identity.telegram_user_id)
    )
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Loyalty profile not found"
        )
    return customer


CustomerDependency = Annotated[Customer, Depends(get_current_customer)]


async def require_sales_admin(
    session: SessionDependency,
    identity: IdentityDependency,
) -> AdminUser:
    """Allow active sales users and the owner."""
    admin = await session.get(AdminUser, identity.telegram_user_id)
    if admin is None or not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Administrator access required"
        )
    return admin


SalesAdminDependency = Annotated[AdminUser, Depends(require_sales_admin)]


async def require_owner(
    admin: SalesAdminDependency,
) -> AdminUser:
    """Allow owner-only configuration, search and exports."""
    if admin.role is not AdminRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner access required")
    return admin


OwnerDependency = Annotated[AdminUser, Depends(require_owner)]
