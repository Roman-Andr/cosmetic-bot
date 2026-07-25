from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.admin import PurchaseRecordRequest


def test_sales_purchase_request_accepts_optional_multiple_products() -> None:
    request = PurchaseRecordRequest(
        buyer_code="123456",
        total_amount=Decimal("49.90"),
        product_external_ids=["tilda-1", "tilda-2"],
    )

    assert request.buyer_code == "123456"
    assert request.product_external_ids == ["tilda-1", "tilda-2"]


@pytest.mark.parametrize("buyer_code", ["12345", "1234567", "abcdef"])
def test_sales_purchase_request_rejects_malformed_customer_code(buyer_code: str) -> None:
    with pytest.raises(ValidationError):
        PurchaseRecordRequest(buyer_code=buyer_code, total_amount=Decimal("1.00"))
