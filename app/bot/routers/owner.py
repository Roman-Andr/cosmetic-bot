"""Owner-only administration, reports, customer search, and tier configuration."""

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy import func, select

from app.bot.keyboards import owner_menu
from app.bot.routers.access import get_admin_role, require_owner_message
from app.bot.states import OwnerStates
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import AdminRole, AdminUser, Customer, LoyaltyAccount, Purchase
from app.services.customer_search import search_customer_accounts
from app.services.reports import customer_report, purchase_report
from app.services.tier_rules import list_active_tiers, parse_tier_rules, replace_active_tiers

router = Router(name="owner-workflows")
settings = get_settings()


@router.message(Command("admin"))
async def owner_panel(message: Message) -> None:
    """Show owner controls without exposing them to sales-only administrators."""
    if not await require_owner_message(message):
        return
    await message.answer(
        "Панель главного администратора\n\n"
        "Команды: /stats, /find, /admins, /addsales, /tiers, "
        "/exportcustomers, /exportpurchases",
        reply_markup=owner_menu(settings.public_base_url),
    )


async def owner_stats_text() -> str:
    """Build one all-time snapshot for both the bot button and the /stats command."""
    async with SessionLocal() as session:
        registrations = await session.scalar(select(func.count(Customer.id)))
        purchase_count = await session.scalar(select(func.count(Purchase.id)))
        turnover = await session.scalar(
            select(func.coalesce(func.sum(LoyaltyAccount.lifetime_turnover), 0))
        )
        liability = await session.scalar(
            select(func.coalesce(func.sum(LoyaltyAccount.current_balance), 0))
        )
    return (
        "Статистика за всё время:\n"
        f"Клиентов: {registrations or 0}\n"
        f"Покупок: {purchase_count or 0}\n"
        f"Оборот: {turnover or 0} BYN\n"
        f"Бонусные обязательства: {liability or 0} BYN"
    )


@router.callback_query(F.data == "owner:stats")
async def owner_stats(callback: CallbackQuery) -> None:
    """Show essential all-time metrics directly in the bot."""
    if (
        callback.from_user is None
        or await get_admin_role(callback.from_user.id) is not AdminRole.OWNER
    ):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    await callback.answer()
    if callback.message:
        await callback.message.answer(await owner_stats_text())


@router.message(Command("stats"))
async def owner_stats_command(message: Message) -> None:
    """Expose the owner dashboard summary directly as a discoverable command."""
    if not await require_owner_message(message):
        return
    await message.answer(await owner_stats_text())


@router.message(Command("admins"))
async def owner_administrators_command(message: Message) -> None:
    """List the current owner and sales accounts without requiring the Mini App."""
    if not await require_owner_message(message):
        return
    async with SessionLocal() as session:
        administrators = list(
            (await session.scalars(select(AdminUser).order_by(AdminUser.created_at))).all()
        )
    if not administrators:
        await message.answer("Администраторы пока не добавлены.")
        return
    lines = [
        f"• <code>{admin.telegram_user_id}</code> — "
        f"{'главный' if admin.role is AdminRole.OWNER else 'продажи'}"
        for admin in administrators
        if admin.is_active
    ]
    await message.answer("Администраторы:\n" + "\n".join(lines), parse_mode="HTML")


@router.message(Command("find"))
async def owner_find_customer_command(message: Message, command: CommandObject) -> None:
    """Find loyalty customers by name, phone, or an active six-digit code in the bot."""
    if not await require_owner_message(message):
        return
    query = (command.args or "").strip()
    if len(query) < 2:
        await message.answer(
            "Используйте: <code>/find ФИО, телефон или код</code>",
            parse_mode="HTML",
        )
        return
    async with SessionLocal() as session:
        rows = await search_customer_accounts(
            session,
            query,
            code_pepper=settings.loyalty_code_pepper,
            limit=20,
        )
    if not rows:
        await message.answer("Клиенты не найдены.")
        return
    lines = [
        f"• {customer.full_name} — {customer.phone}\n"
        f"  Баланс: {account.current_balance} BYN · Оборот: {account.lifetime_turnover} BYN"
        for customer, account in rows
    ]
    await message.answer("Результаты поиска:\n" + "\n".join(lines))


@router.message(Command("exportcustomers"))
async def owner_export_customers_command(message: Message) -> None:
    """Send the owner the same customer XLSX export available in the Mini App."""
    if not await require_owner_message(message):
        return
    async with SessionLocal() as session:
        content = await customer_report(session)
    await message.answer_document(
        BufferedInputFile(content, filename="customers.xlsx"),
        caption="Выгрузка клиентов",
    )


@router.message(Command("exportpurchases"))
async def owner_export_purchases_command(message: Message) -> None:
    """Send the owner the same immutable purchase report available in the Mini App."""
    if not await require_owner_message(message):
        return
    async with SessionLocal() as session:
        content = await purchase_report(session)
    await message.answer_document(
        BufferedInputFile(content, filename="purchases.xlsx"),
        caption="Выгрузка покупок",
    )


@router.callback_query(F.data == "owner:add-sales")
async def owner_add_sales_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Request a sales administrator's numeric Telegram ID."""
    if (
        callback.from_user is None
        or await get_admin_role(callback.from_user.id) is not AdminRole.OWNER
    ):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    await state.set_state(OwnerStates.sales_admin_id)
    await callback.answer()
    if callback.message:
        await callback.message.answer("Введите Telegram ID администратора продаж.")


@router.message(Command("addsales"))
async def owner_add_sales_command(message: Message, state: FSMContext) -> None:
    """Expose the same sales-admin workflow through an owner command."""
    if not await require_owner_message(message):
        return
    await state.set_state(OwnerStates.sales_admin_id)
    await message.answer("Введите Telegram ID администратора продаж.")


@router.message(OwnerStates.sales_admin_id, F.text)
async def owner_add_sales_finish(message: Message, state: FSMContext) -> None:
    """Grant sales-only access from the owner bot panel."""
    if not await require_owner_message(message):
        return
    if message.from_user is None:
        return
    try:
        telegram_user_id = int((message.text or "").strip())
        if telegram_user_id <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите положительный числовой Telegram ID.")
        return
    async with SessionLocal() as session:
        existing = await session.get(AdminUser, telegram_user_id)
        if existing is None:
            session.add(
                AdminUser(
                    telegram_user_id=telegram_user_id,
                    role=AdminRole.SALES,
                    added_by_telegram_id=message.from_user.id,
                )
            )
        elif existing.role is not AdminRole.OWNER:
            existing.role = AdminRole.SALES
            existing.is_active = True
            existing.added_by_telegram_id = message.from_user.id
        else:
            await message.answer("Этот ID уже принадлежит главному администратору.")
            return
        await session.commit()
    await state.clear()
    await message.answer("Администратор продаж добавлен.")


@router.callback_query(F.data == "owner:tiers")
async def owner_tiers_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Let the owner update the cashback table in the bot as well as the Mini App."""
    if (
        callback.from_user is None
        or await get_admin_role(callback.from_user.id) is not AdminRole.OWNER
    ):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    async with SessionLocal() as session:
        tiers = await list_active_tiers(session)
    current = ", ".join(f"{tier.minimum_turnover}:{tier.cashback_percent}" for tier in tiers)
    await state.set_state(OwnerStates.tier_rules)
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "Отправьте уровни в формате <code>порог:процент, порог:процент</code>.\n"
            "Первый порог должен быть 0. Изменение повлияет только на будущие начисления.\n"
            f"Сейчас: <code>{current}</code>",
            parse_mode="HTML",
        )


@router.message(Command("tiers"))
async def owner_tiers_command(message: Message, state: FSMContext) -> None:
    """Expose the tier workflow through a discoverable owner command."""
    if not await require_owner_message(message):
        return
    await state.set_state(OwnerStates.tier_rules)
    await message.answer(
        "Отправьте уровни, например: <code>0:3, 1000:5, 2000:7</code>",
        parse_mode="HTML",
    )


@router.message(OwnerStates.tier_rules, F.text)
async def owner_tiers_finish(message: Message, state: FSMContext) -> None:
    """Atomically replace tier rules and retain an owner audit trail."""
    if not await require_owner_message(message) or message.from_user is None:
        return
    try:
        rules = parse_tier_rules(message.text or "")
    except ValueError as exc:
        await message.answer(f"Не удалось сохранить уровни: {exc}")
        return
    async with SessionLocal() as session:
        await replace_active_tiers(
            session,
            rules,
            actor_telegram_id=message.from_user.id,
        )
    await state.clear()
    await message.answer("Уровни кешбэка сохранены. Они будут применяться к будущим покупкам.")
