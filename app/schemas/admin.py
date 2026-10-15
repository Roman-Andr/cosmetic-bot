"""Owner and sales-administration API contracts."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models import AdminRole, CampaignStatus, CashbackSource


class ProductResponse(BaseModel):
    """Product search result available while recording a purchase."""

    external_id: str
    title: str
    current_price: Decimal | None


class AdminAccessResponse(BaseModel):
    """The current caller's administrative role, if Telegram authentication succeeds."""

    role: AdminRole


class PurchasePreviewRequest(BaseModel):
    """Sale input collected in the bot or in the administrative Mini App."""

    buyer_code: str = Field(pattern=r"^\d{6}$")
    total_amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class BuyerLookupResponse(BaseModel):
    """Customer information shown as soon as an administrator enters a valid code."""

    customer_name: str
    customer_phone_masked: str
    registered_at: datetime
    current_balance: Decimal
    cashback_percent: Decimal
    cashback_source: CashbackSource


class PurchasePreviewResponse(BaseModel):
    """Privacy-minimised sale preview returned before an irreversible confirmation."""

    customer_name: str
    customer_phone_masked: str
    current_balance: Decimal
    total_amount: Decimal
    bonus_redeemed: Decimal
    cash_paid: Decimal
    cashback_accrued: Decimal
    cashback_percent: Decimal
    cashback_source: CashbackSource


class PurchaseRecordRequest(PurchasePreviewRequest):
    """Confirmed sale with an optional set of catalogue product identifiers."""

    product_external_ids: list[str] = Field(default_factory=list, max_length=30)


class PurchaseRecordResponse(BaseModel):
    """The immutable purchase result for the administrative Mini App."""

    purchase_id: UUID
    bonus_redeemed: Decimal
    cash_paid: Decimal
    cashback_accrued: Decimal
    cashback_percent: Decimal
    cashback_source: CashbackSource
    balance_after: Decimal


class CustomerSearchResponse(BaseModel):
    """Owner-visible customer search result."""

    customer_id: UUID
    full_name: str
    phone: str
    telegram_user_id: int
    registered_at: datetime
    current_balance: Decimal
    lifetime_turnover: Decimal


class CustomerDetailResponse(CustomerSearchResponse):
    """Expanded owner-visible customer card."""

    birth_date: date
    gender: str


class AdminStatsResponse(BaseModel):
    """Dashboard aggregates for an optional date range."""

    registrations: int
    purchase_count: int
    turnover: Decimal
    accrued_bonuses: Decimal
    redeemed_bonuses: Decimal
    bonus_liability: Decimal
    tier_distribution: dict[str, int]


class TierRuleInput(BaseModel):
    """One owner-editable cashback threshold."""

    minimum_turnover: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    cashback_percent: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)


class TierRulesUpdateRequest(BaseModel):
    """The complete sorted tier table submitted by the owner."""

    rules: list[TierRuleInput] = Field(min_length=1, max_length=10)

    @field_validator("rules")
    @classmethod
    def rules_start_at_zero_and_are_unique(cls, rules: list[TierRuleInput]) -> list[TierRuleInput]:
        thresholds = [rule.minimum_turnover for rule in rules]
        if thresholds[0] != 0:
            raise ValueError("The first tier must start at 0 BYN")
        if thresholds != sorted(thresholds) or len(set(thresholds)) != len(thresholds):
            raise ValueError("Tier thresholds must be strictly increasing")
        return rules


class TierRuleResponse(TierRuleInput):
    """A persisted active tier rule."""

    id: int


class AddSalesAdminRequest(BaseModel):
    """Owner request to grant sales-only access to a Telegram account."""

    telegram_user_id: int = Field(gt=0)


class AdminUserResponse(BaseModel):
    """Administrator role record."""

    telegram_user_id: int
    role: str
    is_active: bool
    created_at: datetime


class CampaignCreateRequest(BaseModel):
    """Owner input for a scheduled promotion; business rules are checked by the service."""

    title: str = Field(min_length=2, max_length=100)
    message_text: str = Field(min_length=1, max_length=4096)
    photo_file_id: str | None = Field(default=None, min_length=1, max_length=255)
    bonus_amount: Decimal = Field(ge=0, le=1000, max_digits=10, decimal_places=2)
    bonus_valid_until: date | None = None
    starts_at: datetime

    @field_validator("title", "message_text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Text must not be blank")
        return stripped


class CampaignUpdateRequest(CampaignCreateRequest):
    """New values for a scheduled campaign; ``keep_photo`` reuses the picture already stored."""

    keep_photo: bool = False

    @model_validator(mode="after")
    def photo_is_kept_or_replaced(self) -> "CampaignUpdateRequest":
        if self.keep_photo and self.photo_file_id is not None:
            raise ValueError("Either keep the current photo or send a new one, not both")
        return self


class CampaignPreviewResponse(BaseModel):
    """The exact message customers will receive and the size of the audience."""

    message_text: str
    audience_size: int
    total_bonus: Decimal


class CampaignResponse(BaseModel):
    """A persisted promotion campaign as shown in the owner dashboard."""

    id: UUID
    title: str
    message_text: str
    owner_text: str
    has_photo: bool
    bonus_amount: Decimal
    bonus_valid_until: date | None
    starts_at: datetime
    status: CampaignStatus
    recipients_count: int | None
    late_recipients_count: int
    launched_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime


class CampaignLateDeliveryResponse(BaseModel):
    """How many customers who joined after the launch have just been sent the campaign."""

    recipients: int


class CampaignListResponse(BaseModel):
    """Campaign history plus the current number of customers a new campaign would reach."""

    audience_size: int
    items: list[CampaignResponse]


class CampaignPhotoUploadRequest(BaseModel):
    """A base64-encoded JPEG or PNG resized by the Mini App before upload."""

    image_base64: str = Field(min_length=1, max_length=7_000_000)


class CampaignPhotoUploadResponse(BaseModel):
    """Telegram's reusable identifier for the uploaded campaign picture."""

    photo_file_id: str
