"""Bonus lot expiry dates and soonest-expiring-first debit allocation."""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.services.loyalty import (
    MINSK_TIMEZONE,
    BonusExpiration,
    BonusLot,
    LoyaltyError,
    accrual_expires_at,
    add_months,
    allocate_debit,
    expiry_instant,
    next_expiration,
    usable_balance,
    valid_until,
)

NOW = datetime(2026, 10, 13, 10, 0, tzinfo=MINSK_TIMEZONE).astimezone(UTC)


def lot(remaining: str, valid_through: date, *, created_at: datetime = NOW) -> BonusLot:
    return BonusLot(
        transaction_id=uuid.uuid4(),
        remaining=Decimal(remaining),
        expires_at=expiry_instant(valid_through),
        created_at=created_at,
    )


@pytest.mark.parametrize(
    ("value", "months", "expected"),
    [
        (date(2026, 10, 13), 6, date(2027, 4, 13)),
        (date(2026, 8, 31), 6, date(2027, 2, 28)),
        (date(2027, 8, 31), 6, date(2028, 2, 29)),
        (date(2026, 12, 15), 1, date(2027, 1, 15)),
    ],
)
def test_add_months_clamps_to_the_end_of_a_shorter_month(
    value: date, months: int, expected: date
) -> None:
    assert add_months(value, months) == expected


def test_accrual_stays_valid_through_the_same_minsk_day_six_months_later() -> None:
    expires_at = accrual_expires_at(NOW, lifetime_months=6)

    assert expires_at == datetime(2027, 4, 14, tzinfo=MINSK_TIMEZONE)
    assert valid_until(expires_at) == date(2027, 4, 13)


def test_accrual_lifetime_uses_the_minsk_calendar_date_rather_than_utc() -> None:
    late_evening_utc = datetime(2026, 10, 13, 22, 30, tzinfo=UTC)  # 14.10 01:30 in Minsk

    assert valid_until(accrual_expires_at(late_evening_utc, lifetime_months=6)) == date(2027, 4, 14)


def test_expiry_instant_is_the_local_midnight_after_the_last_valid_day() -> None:
    expires_at = expiry_instant(date(2026, 10, 16))

    assert expires_at == datetime(2026, 10, 17, tzinfo=MINSK_TIMEZONE)
    assert valid_until(expires_at) == date(2026, 10, 16)
    assert valid_until(expires_at - timedelta(microseconds=1)) == date(2026, 10, 16)


def test_debit_consumes_the_soonest_expiring_lot_first() -> None:
    old_accrual = lot("10.00", date(2027, 4, 13), created_at=NOW - timedelta(days=30))
    gift = lot("5.00", date(2026, 10, 16))

    allocations = allocate_debit([old_accrual, gift], Decimal("7.00"))

    assert allocations == [
        (gift.transaction_id, Decimal("5.00")),
        (old_accrual.transaction_id, Decimal("2.00")),
    ]


def test_debit_breaks_expiry_ties_by_the_oldest_credit() -> None:
    newer = lot("3.00", date(2027, 4, 13))
    older = lot("3.00", date(2027, 4, 13), created_at=NOW - timedelta(days=1))

    assert allocate_debit([newer, older], Decimal("4.00")) == [
        (older.transaction_id, Decimal("3.00")),
        (newer.transaction_id, Decimal("1.00")),
    ]


def test_debit_larger_than_open_lots_is_rejected() -> None:
    with pytest.raises(LoyaltyError):
        allocate_debit([lot("1.00", date(2027, 4, 13))], Decimal("1.01"))


def test_zero_debit_allocates_nothing() -> None:
    assert allocate_debit([lot("1.00", date(2027, 4, 13))], Decimal("0")) == []


def test_usable_balance_excludes_lots_past_expiry_that_are_not_swept_yet() -> None:
    expired = lot("4.00", date(2026, 10, 12))
    live = lot("6.00", date(2027, 4, 13))

    assert usable_balance(Decimal("10.00"), [expired, live], NOW) == Decimal("6.00")
    assert usable_balance(Decimal("6.00"), [live], NOW) == Decimal("6.00")


def test_next_expiration_totals_every_lot_ending_on_the_first_day() -> None:
    lots = [
        lot("2.50", date(2026, 10, 16)),
        lot("7.50", date(2026, 10, 16)),
        lot("20.00", date(2027, 4, 13)),
        lot("9.00", date(2026, 10, 12)),  # already past expiry
    ]

    assert next_expiration(lots, NOW) == BonusExpiration(
        amount=Decimal("10.00"), valid_until=date(2026, 10, 16)
    )


def test_next_expiration_is_empty_without_spendable_lots() -> None:
    assert next_expiration([], NOW) is None
    assert next_expiration([lot("1.00", date(2026, 10, 12))], NOW) is None


lot_strategy = st.builds(
    lambda remaining, days: lot(str(remaining), date(2026, 10, 14) + timedelta(days=days)),
    st.decimals(min_value=Decimal("0.01"), max_value=Decimal("500"), places=2),
    st.integers(min_value=0, max_value=400),
)


@given(lots=st.lists(lot_strategy, min_size=1, max_size=12), data=st.data())
def test_allocation_covers_the_debit_exactly_and_respects_expiry_order(
    lots: list[BonusLot], data: st.DataObject
) -> None:
    total = sum((item.remaining for item in lots), Decimal("0"))
    amount = data.draw(st.decimals(min_value=Decimal("0.01"), max_value=total, places=2))

    allocations = allocate_debit(lots, amount)

    by_id = {item.transaction_id: item for item in lots}
    assert sum((portion for _, portion in allocations), Decimal("0")) == amount
    assert all(Decimal("0") < portion <= by_id[credit].remaining for credit, portion in allocations)
    # Every lot except the last one touched is fully consumed, and nothing that
    # expires later than an untouched lot is ever charged first.
    for credit, portion in allocations[:-1]:
        assert portion == by_id[credit].remaining
    touched = {credit for credit, _ in allocations}
    latest_touched = max(by_id[credit].expires_at for credit in touched)
    assert all(
        item.expires_at >= latest_touched for item in lots if item.transaction_id not in touched
    )
