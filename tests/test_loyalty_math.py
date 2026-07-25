from decimal import Decimal

from app.services.loyalty import MAX_BONUS_SHARE, calculate_purchase_amounts, money


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
