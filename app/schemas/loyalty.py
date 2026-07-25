"""Mini App request and response contracts."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models import Gender


class RegistrationRequest(BaseModel):
    """Customer details collected after Telegram contact sharing."""

    full_name: str = Field(min_length=2, max_length=255)
    birth_date: date = Field(description="ISO date supplied by the Mini App")
    gender: Gender


class FullNameUpdateRequest(BaseModel):
    """The only personal field a customer may edit after registration."""

    full_name: str = Field(min_length=2, max_length=255)


class TierResponse(BaseModel):
    """Current tier determined from all-time turnover."""

    minimum_turnover: Decimal
    cashback_percent: Decimal


class PurchaseSummaryResponse(BaseModel):
    """Customer-visible purchase history row."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    total_amount: Decimal
    bonus_redeemed: Decimal
    cashback_accrued: Decimal


class ProfileResponse(BaseModel):
    """Loyalty profile returned to the Mini App."""

    full_name: str
    phone: str
    birth_date: date
    gender: Gender
    registered_at: datetime
    current_balance: Decimal
    lifetime_turnover: Decimal
    tier: TierResponse


class ContactStatusResponse(BaseModel):
    """Whether a fresh Telegram contact share is ready for registration."""

    is_available: bool


class CodeResponse(BaseModel):
    """A plaintext code returned once to the authenticated customer."""

    code: str = Field(pattern=r"^\d{6}$")
    expires_at: datetime


class PurchasePageResponse(BaseModel):
    """Paginated customer purchase history."""

    items: list[PurchaseSummaryResponse]
    next_offset: int | None
