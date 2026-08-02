"""Owner-only customer lookup shared by HTTP and Telegram interfaces."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Customer, LoyaltyAccount, LoyaltyCode
from app.services.loyalty import SecretValue, code_digest

CustomerAccountRow = tuple[Customer, LoyaltyAccount]


async def search_customer_accounts(
    session: AsyncSession,
    query: str,
    *,
    code_pepper: SecretValue,
    limit: int,
) -> list[CustomerAccountRow]:
    """Find customers by name/phone, preferring an exact temporary-code match."""
    term = query.strip()
    result = await session.execute(
        select(Customer, LoyaltyAccount)
        .join(LoyaltyAccount, LoyaltyAccount.customer_id == Customer.id)
        .where(
            or_(
                Customer.full_name.ilike(f"%{term}%"),
                Customer.phone.ilike(f"%{term}%"),
            )
        )
        .order_by(Customer.full_name)
        .limit(limit)
    )
    rows = [(customer, account) for customer, account in result]

    if term.isdigit() and len(term) == 6:
        now = datetime.now(UTC)
        code_result = await session.execute(
            select(Customer, LoyaltyAccount)
            .join(LoyaltyAccount, LoyaltyAccount.customer_id == Customer.id)
            .join(LoyaltyCode, LoyaltyCode.account_id == LoyaltyAccount.id)
            .where(
                LoyaltyCode.code_digest == code_digest(term, code_pepper),
                LoyaltyCode.used_at.is_(None),
                LoyaltyCode.expires_at > now,
            )
        )
        code_rows = [(customer, account) for customer, account in code_result]
        return code_rows or rows
    return rows
