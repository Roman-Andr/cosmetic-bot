"""Customer entry points, product deep links, registration, and loyalty codes."""

from datetime import UTC, datetime

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from app.bot.keyboards import customer_menu, loyalty_web_app_keyboard
from app.bot.routers.access import require_sales
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import ContactShare, Customer, LoyaltyAccount, Product
from app.services.customer_data import InvalidPhoneError, normalize_phone
from app.services.loyalty import LoyaltyService

router = Router(name="customer-workflows")
settings = get_settings()


@router.message(CommandStart())
async def start(message: Message, command: CommandObject) -> None:
    """Keep product deep links and add the generic loyalty entry link."""
    if message.from_user is None:
        return
    payload = (command.args or "").strip()
    if payload == "loyalty":
        await message.answer(
            "Добро пожаловать в программу лояльности Velina Cosmetic.",
            reply_markup=loyalty_web_app_keyboard(settings.public_base_url),
        )
        return
    if not payload:
        await message.answer(
            "Откройте программу лояльности или перейдите по ссылке на товар.",
            reply_markup=customer_menu(),
        )
        return

    async with SessionLocal() as session:
        product = await session.scalar(
            select(Product).where(Product.external_id == payload, Product.is_active.is_(True))
        )
    if product is None:
        await message.answer("Товар не найден. Откройте программу лояльности через меню.")
        return

    text = f"{product.title}\n\nСтоимость: {product.current_price or 'уточняйте'} BYN"
    keyboard_rows: list[list[InlineKeyboardButton]] = []
    if product.url:
        keyboard_rows.append([InlineKeyboardButton(text="Добавить в корзину", url=product.url)])
    keyboard_rows.append(
        [InlineKeyboardButton(text="Нужна помощь", callback_data=f"support:{product.id}")]
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    if product.photo_url:
        await message.answer_photo(product.photo_url, caption=text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)


@router.message(Command("id"))
async def show_telegram_id(message: Message) -> None:
    """Return the sender's numeric Telegram ID for administrator onboarding."""
    if message.from_user is None:
        return
    await message.answer(
        f"Ваш Telegram ID: <code>{message.from_user.id}</code>\n"
        "Отправьте его главному администратору для выдачи доступа.",
        parse_mode="HTML",
    )


@router.message(F.contact)
async def contact_shared(message: Message) -> None:
    """Persist a phone number only when Telegram confirms it belongs to the sender."""
    if message.from_user is None or message.contact is None:
        return
    if message.contact.user_id != message.from_user.id:
        await message.answer("Пожалуйста, поделитесь своим собственным номером телефона.")
        return
    try:
        phone = normalize_phone(message.contact.phone_number)
    except InvalidPhoneError:
        await message.answer("Telegram передал некорректный номер телефона.")
        return
    async with SessionLocal() as session:
        share = await session.get(ContactShare, message.from_user.id)
        if share is None:
            session.add(ContactShare(telegram_user_id=message.from_user.id, phone=phone))
        else:
            share.phone = phone
            share.shared_at = datetime.now(UTC)
        await session.commit()
    await message.answer("Номер получен. Вернитесь в Mini App и завершите регистрацию.")


@router.message(F.text == "Программа лояльности")
@router.message(Command("loyalty"))
async def open_loyalty(message: Message) -> None:
    """Open the Mini App from a standard bot menu action."""
    await message.answer(
        "Ваш баланс, история покупок и регистрация доступны в Mini App.",
        reply_markup=loyalty_web_app_keyboard(settings.public_base_url),
    )


@router.message(Command("work"))
async def open_sales_workplace(message: Message) -> None:
    """Give sales users a direct, role-checked entry point to their Mini App workspace."""
    if not await require_sales(message):
        return
    await message.answer(
        "Откройте рабочий кабинет для оформления покупки.",
        reply_markup=loyalty_web_app_keyboard(settings.public_base_url),
    )


@router.message(F.text == "Получить код")
@router.message(Command("code"))
async def get_customer_code(message: Message) -> None:
    """Provide the same one-hour code flow as the Mini App."""
    if message.from_user is None:
        return
    async with SessionLocal() as session:
        account_id = await session.scalar(
            select(LoyaltyAccount.id)
            .join(Customer, Customer.id == LoyaltyAccount.customer_id)
            .where(Customer.telegram_user_id == message.from_user.id)
        )
        if account_id is None:
            await message.answer(
                "Сначала зарегистрируйтесь в программе лояльности.",
                reply_markup=loyalty_web_app_keyboard(settings.public_base_url),
            )
            return
        code, expires_at = await LoyaltyService(settings).generate_code(session, account_id)
    await message.answer(
        f"Ваш код: <code>{code}</code>\nДействует до {expires_at.astimezone().strftime('%H:%M')}.",
        parse_mode="HTML",
    )
