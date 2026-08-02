"""Property-based tests for the money invariants the domain depends on.

These target the two "load-bearing" invariants documented for LoyaltyService: the
10% redemption cap (accrual only on the cash-paid remainder) and the birthday-window
calendar arithmetic (including the 29 February observed-day rule). Hypothesis is used
here, rather than more example tests, because the interesting bugs in rounding and
calendar edge cases tend to live at inputs a human wouldn't think to write by hand.
"""

from datetime import date
from decimal import ROUND_DOWN, Decimal

from hypothesis import given
from hypothesis import strategies as st

from app.services.loyalty import (
    MAX_BONUS_SHARE,
    calculate_purchase_amounts,
    is_birthday_cashback_active,
    money,
    observed_birthday,
)

money_amounts = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("1000000"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)
balances = st.decimals(
    min_value=Decimal("0.00"),
    max_value=Decimal("1000000"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)
percents = st.decimals(
    min_value=Decimal("0.00"),
    max_value=Decimal("100.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)


@given(current_balance=balances, total_amount=money_amounts, cashback_percent=percents)
def test_redemption_never_exceeds_ten_percent_of_the_total(
    current_balance: Decimal, total_amount: Decimal, cashback_percent: Decimal
) -> None:
    amounts = calculate_purchase_amounts(
        current_balance=current_balance,
        total_amount=total_amount,
        cashback_percent=cashback_percent,
    )
    cap = money(total_amount * MAX_BONUS_SHARE, rounding=ROUND_DOWN)
    assert amounts.redeemed <= cap


@given(current_balance=balances, total_amount=money_amounts, cashback_percent=percents)
def test_redemption_never_exceeds_the_available_balance(
    current_balance: Decimal, total_amount: Decimal, cashback_percent: Decimal
) -> None:
    amounts = calculate_purchase_amounts(
        current_balance=current_balance,
        total_amount=total_amount,
        cashback_percent=cashback_percent,
    )
    assert amounts.redeemed <= money(current_balance)


@given(current_balance=balances, total_amount=money_amounts, cashback_percent=percents)
def test_cash_paid_and_redeemed_always_reconstruct_the_total(
    current_balance: Decimal, total_amount: Decimal, cashback_percent: Decimal
) -> None:
    amounts = calculate_purchase_amounts(
        current_balance=current_balance,
        total_amount=total_amount,
        cashback_percent=cashback_percent,
    )
    assert amounts.cash_paid + amounts.redeemed == money(total_amount)


@given(current_balance=balances, total_amount=money_amounts, cashback_percent=percents)
def test_balance_after_never_goes_negative(
    current_balance: Decimal, total_amount: Decimal, cashback_percent: Decimal
) -> None:
    amounts = calculate_purchase_amounts(
        current_balance=current_balance,
        total_amount=total_amount,
        cashback_percent=cashback_percent,
    )
    assert amounts.balance_after >= Decimal("0.00")
    assert amounts.balance_after == money(current_balance - amounts.redeemed + amounts.accrued)


birth_dates = st.dates(min_value=date(1900, 1, 1), max_value=date(2020, 12, 31))
observed_years = st.integers(min_value=1901, max_value=2100)
window_days = st.integers(min_value=0, max_value=31)


@given(birth_date=birth_dates, year=observed_years, window=window_days)
def test_the_observed_birthday_itself_is_always_inside_its_own_window(
    birth_date: date, year: int, window: int
) -> None:
    purchase_date = observed_birthday(birth_date, year)
    assert is_birthday_cashback_active(birth_date, purchase_date, window_days=window)


@given(birth_date=birth_dates, year=observed_years)
def test_observed_birthday_falls_in_the_requested_calendar_year(
    birth_date: date, year: int
) -> None:
    assert observed_birthday(birth_date, year).year == year


@given(birth_date=birth_dates, year=observed_years)
def test_leap_day_birthdays_only_ever_observe_on_28_or_29_february(
    birth_date: date, year: int
) -> None:
    if birth_date.month == 2 and birth_date.day == 29:
        observed = observed_birthday(birth_date, year)
        assert observed.month == 2
        assert observed.day in (28, 29)
