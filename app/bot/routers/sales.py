"""Sales administrator purchase workflow handlers."""

from decimal import InvalidOperation
from uuid import UUID

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from app.bot.keyboards import sale_confirmation_keyboard, sale_product_keyboard
from app.bot.routers.access import require_sales
from app.bot.states import SaleStates
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Product
from app.services.customer_data import mask_phone
from app.services.loyalty import (
    InvalidCodeError,
    LoyaltyError,
    LoyaltyService,
    ProductSelection,
    money,
)

router = Router(name="sales-workflows")
settings = get_settings()


@router.message(Command("sale"))
async def start_sale(message: Message, state: FSMContext) -> None:
    """Start a role-protected sale draft in Redis."""
    if not await require_sales(message):
        return
    await state.clear()
    await state.set_state(SaleStates.buyer_code)
    await message.answer("Введите 6-значный код покупателя.")


@router.message(SaleStates.buyer_code, F.text)
async def sale_buyer_code(message: Message, state: FSMContext) -> None:
    """Validate code shape before requesting the order total."""
    code = (message.text or "").strip()
    if not code.isdigit() or len(code) != 6:
        await message.answer("Код должен состоять из шести цифр.")
        return
    await state.update_data(buyer_code=code)
    await state.set_state(SaleStates.total_amount)
    await message.answer("Введите полную сумму покупки в BYN.")


@router.message(SaleStates.total_amount, F.text)
async def sale_total_amount(message: Message, state: FSMContext) -> None:
    """Validate the full amount before optional catalogue selection."""
    try:
        total = money((message.text or "").strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        await message.answer("Введите корректную сумму, например 49.90.")
        return
    if total <= 0:
        await message.answer("Сумма должна быть больше нуля.")
        return
    await state.update_data(total_amount=str(total), product_ids=[])
    await state.set_state(SaleStates.products)
    await message.answer(
        "Найдите товар текстом или завершите оформление без товаров.",
        reply_markup=sale_product_keyboard([]),
    )


@router.message(SaleStates.products, F.text)
async def sale_product_search(message: Message, state: FSMContext) -> None:
    """Search locally synchronized products and add them through compact callbacks."""
    query = (message.text or "").strip()
    async with SessionLocal() as session:
        products = list(
            (
                await session.scalars(
                    select(Product)
                    .where(
                        Product.is_active.is_(True),
                        Product.title.ilike(f"%{query}%"),
                    )
                    .order_by(Product.title)
                    .limit(10)
                )
            ).all()
        )
    if not products:
        await message.answer("Товары не найдены. Попробуйте другой запрос или завершите выбор.")
        return
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=product.title[:60], callback_data=f"sale:add:{product.id}")]
            for product in products
        ]
    )
    await message.answer("Выберите товар:", reply_markup=keyboard)


@router.callback_query(SaleStates.products, F.data.startswith("sale:add:"))
async def sale_add_product(callback: CallbackQuery, state: FSMContext) -> None:
    """Add a selected optional product and keep the administrator in search mode."""
    if callback.data is None:
        return
    product_id = callback.data.removeprefix("sale:add:")
    try:
        UUID(product_id)
    except ValueError:
        await callback.answer("Некорректный товар.", show_alert=True)
        return
    data = await state.get_data()
    product_ids = list(dict.fromkeys([*data.get("product_ids", []), product_id]))
    await state.update_data(product_ids=product_ids)
    await callback.answer("Товар добавлен")
    if callback.message:
        await callback.message.answer(
            f"Выбрано товаров: {len(product_ids)}. Ищите следующий или завершите выбор.",
            reply_markup=sale_product_keyboard(product_ids),
        )


@router.callback_query(SaleStates.products, F.data.in_({"sale:skip", "sale:finish"}))
async def sale_preview(callback: CallbackQuery, state: FSMContext) -> None:
    """Show all irreversible sale details before the final confirmation button."""
    data = await state.get_data()
    product_ids = [] if callback.data == "sale:skip" else data.get("product_ids", [])
    async with SessionLocal() as session:
        try:
            preview = await LoyaltyService(settings).preview_purchase(
                session,
                buyer_code=data["buyer_code"],
                total_amount=data["total_amount"],
            )
            product_titles = list(
                (
                    await session.scalars(
                        select(Product.title).where(
                            Product.id.in_([UUID(value) for value in product_ids])
                        )
                    )
                ).all()
            )
        except (InvalidCodeError, LoyaltyError) as exc:
            await state.clear()
            await callback.answer("Код больше не действует.", show_alert=True)
            if callback.message:
                await callback.message.answer(f"Продажа не оформлена: {exc}")
            return
    await state.update_data(product_ids=product_ids)
    await state.set_state(SaleStates.confirmation)
    product_text = ", ".join(product_titles) if product_titles else "не выбраны"
    cashback_label = (
        "кешбэк ко дню рождения"
        if preview.cashback_source.value == "birthday"
        else "уровень лояльности"
    )
    text = (
        "Проверьте продажу:\n\n"
        f"Клиент: {preview.customer_name}, {mask_phone(preview.customer_phone)}\n"
        f"Сумма: {preview.total_amount} BYN\n"
        f"Списать бонусов: {preview.redeemed} BYN\n"
        f"К оплате деньгами: {preview.cash_paid} BYN\n"
        f"Начислить: {preview.accrued} бонусов ({preview.cashback_percent}%, {cashback_label})\n"
        f"Товары: {product_text}"
    )
    await callback.answer()
    if callback.message:
        await callback.message.answer(text, reply_markup=sale_confirmation_keyboard())


@router.callback_query(SaleStates.confirmation, F.data == "sale:confirm")
async def sale_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    """Atomically create the purchase, ledger rows, and notification outbox record."""
    if callback.from_user is None:
        return
    data = await state.get_data()
    async with SessionLocal() as session:
        product_ids = [UUID(value) for value in data.get("product_ids", [])]
        external_ids = list(
            (
                await session.scalars(
                    select(Product.external_id).where(Product.id.in_(product_ids))
                )
            ).all()
        )
        try:
            result = await LoyaltyService(settings).record_purchase(
                session,
                buyer_code=data["buyer_code"],
                recorded_by_telegram_id=callback.from_user.id,
                total_amount=data["total_amount"],
                selected_products=[ProductSelection(external_id=value) for value in external_ids],
            )
        except (InvalidCodeError, LoyaltyError) as exc:
            await state.clear()
            await callback.answer("Продажа не оформлена.", show_alert=True)
            if callback.message:
                await callback.message.answer(str(exc))
            return
    await state.clear()
    await callback.answer("Продажа зафиксирована")
    if callback.message:
        cashback_label = ""
        if result.cashback_source.value == "birthday":
            cashback_label = " по акции ко дню рождения"
        await callback.message.answer(
            "Продажа зафиксирована. "
            f"Списано: {result.redeemed}; начислено: {result.accrued}; "
            f"баланс клиента: {result.balance_after}{cashback_label}."
        )


@router.callback_query(
    StateFilter(SaleStates.products, SaleStates.confirmation), F.data == "sale:cancel"
)
async def sale_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Drop a draft safely before it affects balances or turnover."""
    await state.clear()
    await callback.answer("Черновик отменён")
    if callback.message:
        await callback.message.answer("Оформление продажи отменено.")
