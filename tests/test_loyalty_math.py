from datetime import date
from decimal import Decimal

from app.models import CashbackSource
from app.services.loyalty import (
    MAX_BONUS_SHARE,
    calculate_purchase_amounts,
    effective_cashback,
    is_birthday_cashback_active,
    money,
    observed_birthday,
)


def test_money_rounds_to_two_decimal_places() -> None:
    assert money("1.005") == Decimal("1.01")


def test_bonus_cap_is_ten_percent_of_full_order_amount() -> None:
    assert money(Decimal("129.99") * MAX_BONUS_SHARE) == Decimal("13.00")


def test_redemption_is_capped_and_cashback_uses_cash_remainder() -> None:
    amounts = calculate_purchase_amounts(
        current_balance=Decimal("50.00"),
        total_amount=Decimal("100.00"),
        cashback_percent=Decimal("5.00"),
    )
    assert amounts.redeemed == Decimal("10.00")
    assert amounts.cash_paid == Decimal("90.00")
    assert amounts.accrued == Decimal("4.50")
    assert amounts.balance_after == Decimal("44.50")


def test_birthday_cashback_window_is_inclusive_and_crosses_calendar_year() -> None:
    birthday = date(1992, 1, 1)

    assert is_birthday_cashback_active(birthday, date(2026, 12, 29), window_days=3)
    assert is_birthday_cashback_active(birthday, date(2027, 1, 4), window_days=3)
    assert not is_birthday_cashback_active(birthday, date(2026, 12, 28), window_days=3)
    assert not is_birthday_cashback_active(birthday, date(2027, 1, 5), window_days=3)


def test_leap_day_birthday_is_observed_on_february_28_in_non_leap_years() -> None:
    birthday = date(2000, 2, 29)

    assert observed_birthday(birthday, 2028) == date(2028, 2, 29)
    assert observed_birthday(birthday, 2027) == date(2027, 2, 28)
    assert is_birthday_cashback_active(birthday, date(2027, 3, 3), window_days=3)
    assert not is_birthday_cashback_active(birthday, date(2027, 3, 4), window_days=3)


def test_birthday_cashback_overrides_the_active_tier_rate() -> None:
    rate = effective_cashback(
        tier_percent=Decimal("7.00"),
        birth_date=date(1992, 7, 26),
        purchase_date=date(2026, 7, 23),
        birthday_cashback_percent=Decimal("10.00"),
        birthday_cashback_window_days=3,
    )

    assert rate.percent == Decimal("10.00")
    assert rate.source is CashbackSource.BIRTHDAY
