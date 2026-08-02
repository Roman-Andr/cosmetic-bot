"""Shared loyalty-tier queries, validation, replacement, and audit handling."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent, LoyaltyTierRule

TIER_QUANTUM = Decimal("0.01")


@dataclass(frozen=True)
class TierRuleValue:
    """Persistence-independent representation of one configured loyalty tier."""

    minimum_turnover: Decimal
    cashback_percent: Decimal


def parse_tier_rules(raw: str) -> list[TierRuleValue]:
    """Parse the compact owner-bot syntax and apply the API's ordering constraints."""
    chunks = [chunk.strip() for chunk in raw.split(",") if chunk.strip()]
    if not 1 <= len(chunks) <= 10:
        raise ValueError("Количество уровней должно быть от 1 до 10")

    rules: list[TierRuleValue] = []
    for chunk in chunks:
        threshold_text, separator, percent_text = chunk.partition(":")
        if not separator:
            raise ValueError("Используйте формат порог:процент")
        try:
            threshold = Decimal(threshold_text.strip()).quantize(
                TIER_QUANTUM,
                rounding=ROUND_HALF_UP,
            )
            percent = Decimal(percent_text.strip()).quantize(TIER_QUANTUM)
        except InvalidOperation as exc:
            raise ValueError("Порог и процент должны быть числами") from exc
        if (
            not threshold.is_finite()
            or not percent.is_finite()
            or threshold < 0
            or not Decimal("0") <= percent <= Decimal("100")
        ):
            raise ValueError("Порог должен быть неотрицательным, процент — от 0 до 100")
        rules.append(TierRuleValue(threshold, percent))

    thresholds = [rule.minimum_turnover for rule in rules]
    if (
        thresholds[0] != 0
        or thresholds != sorted(thresholds)
        or len(set(thresholds)) != len(thresholds)
    ):
        raise ValueError("Первый порог должен быть 0, остальные — строго возрастать")
    return rules


async def list_active_tiers(session: AsyncSession) -> list[LoyaltyTierRule]:
    """Return active tiers in ascending threshold order."""
    return list(
        (
            await session.scalars(
                select(LoyaltyTierRule)
                .where(LoyaltyTierRule.is_active.is_(True))
                .order_by(LoyaltyTierRule.minimum_turnover)
            )
        ).all()
    )


async def get_current_tier(
    session: AsyncSession,
    turnover: Decimal,
) -> LoyaltyTierRule | None:
    """Return the highest active tier eligible for the supplied lifetime turnover."""
    tier = await session.scalar(
        select(LoyaltyTierRule)
        .where(
            LoyaltyTierRule.is_active.is_(True),
            LoyaltyTierRule.minimum_turnover <= turnover,
        )
        .order_by(LoyaltyTierRule.minimum_turnover.desc())
        .limit(1)
    )
    return tier


async def replace_active_tiers(
    session: AsyncSession,
    rules: Sequence[TierRuleValue],
    *,
    actor_telegram_id: int,
) -> list[LoyaltyTierRule]:
    """Atomically replace configured tiers and retain the old/new audit payload."""
    try:
        previous = list(
            (
                await session.scalars(
                    select(LoyaltyTierRule).where(LoyaltyTierRule.is_active.is_(True))
                )
            ).all()
        )
        old_payload = [
            {
                "minimum_turnover": str(rule.minimum_turnover),
                "cashback_percent": str(rule.cashback_percent),
            }
            for rule in previous
        ]
        new_payload = [
            {
                "minimum_turnover": str(rule.minimum_turnover),
                "cashback_percent": str(rule.cashback_percent),
            }
            for rule in rules
        ]

        await session.execute(delete(LoyaltyTierRule))
        persisted = [
            LoyaltyTierRule(
                minimum_turnover=rule.minimum_turnover,
                cashback_percent=rule.cashback_percent,
                updated_by_telegram_id=actor_telegram_id,
            )
            for rule in rules
        ]
        session.add_all(persisted)
        session.add(
            AuditEvent(
                actor_telegram_id=actor_telegram_id,
                event_type="loyalty_tiers_replaced",
                target_type="loyalty_tier_rules",
                payload={"old": old_payload, "new": new_payload},
            )
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return persisted
