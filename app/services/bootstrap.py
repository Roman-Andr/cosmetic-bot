"""Idempotent seed data for a freshly migrated deployment."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import AdminRole, AdminUser, LoyaltyTierRule

DEFAULT_TIERS: tuple[tuple[Decimal, Decimal], ...] = (
    (Decimal("0.00"), Decimal("3.00")),
    (Decimal("1000.00"), Decimal("5.00")),
    (Decimal("2000.00"), Decimal("7.00")),
)


async def seed_defaults(session: AsyncSession, settings: Settings) -> None:
    """Seed owner access and default tier rules without overwriting owner changes."""
    async with session.begin():
        owner = await session.get(AdminUser, settings.owner_telegram_id)
        if owner is None:
            session.add(
                AdminUser(
                    telegram_user_id=settings.owner_telegram_id,
                    role=AdminRole.OWNER,
                    added_by_telegram_id=settings.owner_telegram_id,
                )
            )
        elif owner.role is not AdminRole.OWNER:
            owner.role = AdminRole.OWNER
            owner.is_active = True

        existing = set((await session.scalars(select(LoyaltyTierRule.minimum_turnover))).all())
        for minimum_turnover, cashback_percent in DEFAULT_TIERS:
            if minimum_turnover not in existing:
                session.add(
                    LoyaltyTierRule(
                        minimum_turnover=minimum_turnover,
                        cashback_percent=cashback_percent,
                        updated_by_telegram_id=settings.owner_telegram_id,
                    )
                )
