from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models import CashbackSource
from app.schemas.admin import BuyerLookupResponse, PurchaseRecordRequest


def test_sales_purchase_request_accepts_optional_multiple_products() -> None:
    request = PurchaseRecordRequest(
        buyer_code="123456",
        total_amount=Decimal("49.90"),
        product_external_ids=["tilda-1", "tilda-2"],
    )

    assert request.buyer_code == "123456"
    assert request.product_external_ids == ["tilda-1", "tilda-2"]


def test_buyer_lookup_exposes_only_sale_safe_customer_details() -> None:
    lookup = BuyerLookupResponse(
        customer_name="Анна Иванова",
        customer_phone_masked="+375*******12",
        registered_at=datetime(2026, 7, 26, tzinfo=UTC),
        current_balance=Decimal("42.50"),
        cashback_percent=Decimal("5.00"),
        cashback_source=CashbackSource.TIER,
    )

    assert lookup.model_dump() == {
        "customer_name": "Анна Иванова",
        "customer_phone_masked": "+375*******12",
        "registered_at": datetime(2026, 7, 26, tzinfo=UTC),
        "current_balance": Decimal("42.50"),
        "cashback_percent": Decimal("5.00"),
        "cashback_source": CashbackSource.TIER,
    }


@pytest.mark.parametrize("buyer_code", ["12345", "1234567", "abcdef"])
def test_sales_purchase_request_rejects_malformed_customer_code(buyer_code: str) -> None:
    with pytest.raises(ValidationError):
        PurchaseRecordRequest(buyer_code=buyer_code, total_amount=Decimal("1.00"))
