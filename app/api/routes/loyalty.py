"""Customer-facing Mini App loyalty endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.dependencies import (
    CustomerDependency,
    IdentityDependency,
    SessionDependency,
    SettingsDependency,
)
from app.models import ContactShare, Customer, LoyaltyAccount, LoyaltyTierRule, Purchase
from app.schemas.loyalty import (
    CodeResponse,
    ContactStatusResponse,
    FullNameUpdateRequest,
    ProfileResponse,
    PurchasePageResponse,
    PurchaseSummaryResponse,
    RegistrationRequest,
    TierResponse,
)
from app.services.loyalty import LoyaltyService

router = APIRouter(prefix="/loyalty", tags=["loyalty"])
CONTACT_SHARE_TTL = timedelta(minutes=15)


def normalize_phone(phone: str) -> str:
    """Normalize Telegram-provided phone numbers to a stable E.164-like value."""
    digits = "".join(character for character in phone if character.isdigit())
    if len(digits) < 7 or len(digits) > 15:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid phone"
        )
    return f"+{digits}"


async def current_tier(session: SessionDependency, turnover: object) -> LoyaltyTierRule:
    """Load the active rule that applies before the next purchase."""
    tier = await session.scalar(
        select(LoyaltyTierRule)
        .where(LoyaltyTierRule.is_active.is_(True), LoyaltyTierRule.minimum_turnover <= turnover)
        .order_by(LoyaltyTierRule.minimum_turnover.desc())
        .limit(1)
    )
    if tier is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Loyalty programme has no active tiers",
        )
    return tier


async def profile_response(session: SessionDependency, customer: Customer) -> ProfileResponse:
    """Build the customer profile with the dynamically selected loyalty tier."""
    account = await session.scalar(
        select(LoyaltyAccount).where(LoyaltyAccount.customer_id == customer.id)
    )
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Account missing"
        )
    tier = await current_tier(session, account.lifetime_turnover)
    return ProfileResponse(
        full_name=customer.full_name,
        phone=customer.phone,
        birth_date=customer.birth_date,
        gender=customer.gender,
        registered_at=customer.created_at,
        current_balance=account.current_balance,
        lifetime_turnover=account.lifetime_turnover,
        tier=TierResponse(
            minimum_turnover=tier.minimum_turnover,
            cashback_percent=tier.cashback_percent,
        ),
    )


@router.get("/contact-status", response_model=ContactStatusResponse)
async def get_contact_status(
    session: SessionDependency,
    identity: IdentityDependency,
) -> ContactStatusResponse:
    """Tell the Mini App whether Telegram has supplied a fresh contact number."""
    shared_at = await session.scalar(
        select(ContactShare.shared_at).where(
            ContactShare.telegram_user_id == identity.telegram_user_id
        )
    )
    is_available = shared_at is not None and shared_at >= datetime.now(UTC) - CONTACT_SHARE_TTL
    return ContactStatusResponse(is_available=is_available)


@router.post("/register", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegistrationRequest,
    session: SessionDependency,
    identity: IdentityDependency,
) -> ProfileResponse:
    """Create a loyalty profile after a verified Telegram contact share."""
    contact_share = await session.get(ContactShare, identity.telegram_user_id)
    if contact_share is None or contact_share.shared_at < datetime.now(UTC) - CONTACT_SHARE_TTL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Share your phone number in Telegram before registering",
        )

    existing_customer = await session.scalar(
        select(Customer).where(Customer.telegram_user_id == identity.telegram_user_id)
    )
    if existing_customer is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Loyalty profile already exists"
        )

    phone = normalize_phone(contact_share.phone)
    duplicate_phone = await session.scalar(select(Customer.id).where(Customer.phone == phone))
    if duplicate_phone is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This phone number is already registered in the loyalty programme",
        )

    customer = Customer(
        telegram_user_id=identity.telegram_user_id,
        telegram_username=identity.username,
        phone=phone,
        full_name=payload.full_name.strip(),
        birth_date=payload.birth_date,
        gender=payload.gender,
    )
    session.add(customer)
    await session.flush()
    session.add(LoyaltyAccount(customer_id=customer.id))
    await session.delete(contact_share)
    await session.commit()

    return await profile_response(session, customer)


@router.get("/me", response_model=ProfileResponse)
async def get_profile(session: SessionDependency, customer: CustomerDependency) -> ProfileResponse:
    """Return the authenticated customer's loyalty profile."""
    return await profile_response(session, customer)


@router.patch("/me", response_model=ProfileResponse)
async def update_profile(
    payload: FullNameUpdateRequest,
    session: SessionDependency,
    customer: CustomerDependency,
) -> ProfileResponse:
    """Allow only the agreed post-registration full-name change."""
    customer.full_name = payload.full_name.strip()
    await session.commit()
    return await profile_response(session, customer)


@router.post("/code", response_model=CodeResponse)
async def generate_code(
    session: SessionDependency,
    settings: SettingsDependency,
    customer: CustomerDependency,
) -> CodeResponse:
    """Issue a new one-hour buyer code, invalidating the previous active code."""
    account_id = await session.scalar(
        select(LoyaltyAccount.id).where(LoyaltyAccount.customer_id == customer.id)
    )
    if account_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Account missing"
        )
    code, expires_at = await LoyaltyService(settings).generate_code(session, account_id)
    return CodeResponse(code=code, expires_at=expires_at)


@router.get("/purchases", response_model=PurchasePageResponse)
async def get_purchases(
    session: SessionDependency,
    customer: CustomerDependency,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=50),
) -> PurchasePageResponse:
    """List a customer's purchases newest first without exposing admin-only fields."""
    purchases = list(
        (
            await session.scalars(
                select(Purchase)
                .where(Purchase.customer_id == customer.id)
                .order_by(Purchase.created_at.desc())
                .offset(offset)
                .limit(limit + 1)
            )
        ).all()
    )
    next_offset = offset + limit if len(purchases) > limit else None
    return PurchasePageResponse(
        items=[PurchaseSummaryResponse.model_validate(item) for item in purchases[:limit]],
        next_offset=next_offset,
    )
