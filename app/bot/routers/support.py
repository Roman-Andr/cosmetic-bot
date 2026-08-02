"""Customer support dialog and owner moderation handlers."""

from datetime import UTC, datetime
from uuid import UUID

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.bot.keyboards import support_keyboard
from app.bot.routers.access import get_admin_role, is_blocked
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import (
    AdminRole,
    BlockedUser,
    Product,
    SupportDialog,
    SupportDialogStatus,
    SupportForward,
)

router = Router(name="support-workflows")
settings = get_settings()


@router.callback_query(
    F.data.startswith("support:")
    & ~F.data.startswith("support:end:")
    & ~F.data.startswith("support:block:")
    & ~F.data.startswith("support:unblock:")
)
async def open_support(callback: CallbackQuery) -> None:
    """Open or reuse a persistent support dialog for the selected product."""
    if callback.from_user is None or callback.data is None:
        return
    if await is_blocked(callback.from_user.id):
        await callback.answer("Обращения для этого аккаунта ограничены.", show_alert=True)
        return
    product_token = callback.data.removeprefix("support:")
    async with SessionLocal() as session:
        product_external_id: str | None = None
        if product_token != "general":
            try:
                product_id = UUID(product_token)
            except ValueError:
                await callback.answer(
                    "Карточка товара устарела. Откройте её заново.", show_alert=True
                )
                return
            product = await session.get(Product, product_id)
            if product is None or not product.is_active:
                await callback.answer("Товар больше недоступен.", show_alert=True)
                return
            product_external_id = product.external_id
        dialog = await session.scalar(
            select(SupportDialog).where(
                SupportDialog.customer_telegram_id == callback.from_user.id,
                SupportDialog.status == SupportDialogStatus.OPEN,
            )
        )
        if dialog is None:
            dialog = SupportDialog(
                customer_telegram_id=callback.from_user.id,
                customer_name=callback.from_user.full_name,
                product_external_id=product_external_id,
            )
            session.add(dialog)
            await session.commit()
    await callback.answer("Напишите ваш вопрос.")
    if callback.message:
        await callback.message.answer(
            "Напишите ваш вопрос — главный администратор ответит в этом чате."
        )


@router.callback_query(F.data.startswith("support:end:"))
async def close_support(callback: CallbackQuery) -> None:
    """Close a dialog by opaque UUID rather than parsing human-readable text."""
    if (
        callback.from_user is None
        or await get_admin_role(callback.from_user.id) is not AdminRole.OWNER
    ):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    try:
        dialog_id = UUID((callback.data or "").removeprefix("support:end:"))
    except ValueError:
        await callback.answer("Некорректный диалог", show_alert=True)
        return
    async with SessionLocal() as session:
        dialog = await session.get(SupportDialog, dialog_id)
        if dialog is None:
            await callback.answer("Диалог не найден", show_alert=True)
            return
        dialog.status = SupportDialogStatus.CLOSED
        dialog.closed_at = datetime.now(UTC)
        await session.commit()
    await callback.answer("Диалог завершён")
    if callback.bot is not None:
        await callback.bot.send_message(
            dialog.customer_telegram_id,
            "Диалог завершён. Если потребуется помощь, нажмите «Нужна помощь» на карточке товара.",
        )


@router.callback_query(F.data.startswith("support:block:"))
async def block_support_user(callback: CallbackQuery) -> None:
    """Persistently block a user from opening or continuing support dialogs."""
    if (
        callback.from_user is None
        or await get_admin_role(callback.from_user.id) is not AdminRole.OWNER
    ):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    try:
        dialog_id, customer_id = (callback.data or "").removeprefix("support:block:").split(":")
        UUID(dialog_id)
        customer_telegram_id = int(customer_id)
    except ValueError:
        await callback.answer("Некорректный пользователь", show_alert=True)
        return
    async with SessionLocal() as session:
        if await session.get(BlockedUser, customer_telegram_id) is None:
            session.add(
                BlockedUser(
                    telegram_user_id=customer_telegram_id,
                    blocked_by_telegram_id=callback.from_user.id,
                )
            )
        await session.commit()
    await callback.answer("Пользователь заблокирован")
    if isinstance(callback.message, Message):
        await callback.message.edit_reply_markup(
            reply_markup=support_keyboard(dialog_id, customer_telegram_id, is_blocked=True)
        )


@router.callback_query(F.data.startswith("support:unblock:"))
async def unblock_support_user(callback: CallbackQuery) -> None:
    """Restore support access with the same owner-only control path."""
    if (
        callback.from_user is None
        or await get_admin_role(callback.from_user.id) is not AdminRole.OWNER
    ):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    try:
        dialog_id, customer_id = (callback.data or "").removeprefix("support:unblock:").split(":")
        UUID(dialog_id)
        customer_telegram_id = int(customer_id)
    except ValueError:
        await callback.answer("Некорректный пользователь", show_alert=True)
        return
    async with SessionLocal() as session:
        blocked = await session.get(BlockedUser, customer_telegram_id)
        if blocked is not None:
            await session.delete(blocked)
            await session.commit()
    await callback.answer("Пользователь разблокирован")
    if isinstance(callback.message, Message):
        await callback.message.edit_reply_markup(
            reply_markup=support_keyboard(dialog_id, customer_telegram_id)
        )


@router.message(F.reply_to_message)
async def owner_reply_to_support(message: Message, bot: Bot) -> None:
    """Route an owner reply by persistent forwarded-message mapping."""
    if message.from_user is None or message.reply_to_message is None:
        return
    if await get_admin_role(message.from_user.id) is not AdminRole.OWNER:
        return
    async with SessionLocal() as session:
        forward = await session.scalar(
            select(SupportForward).where(
                SupportForward.owner_message_id == message.reply_to_message.message_id
            )
        )
        if forward is None:
            return
        dialog = await session.get(SupportDialog, forward.dialog_id)
        if dialog is None or dialog.status is not SupportDialogStatus.OPEN:
            await message.answer("Этот диалог уже закрыт.")
            return
        customer_telegram_id = dialog.customer_telegram_id
    await bot.copy_message(
        chat_id=customer_telegram_id,
        from_chat_id=message.chat.id,
        message_id=message.message_id,
    )


@router.message()
async def forward_customer_support(message: Message, bot: Bot) -> None:
    """Forward every supported customer message in an open dialog to the owner."""
    if message.from_user is None or message.from_user.id == settings.owner_telegram_id:
        return
    if message.text and message.text.startswith("/"):
        return
    if await is_blocked(message.from_user.id):
        return
    async with SessionLocal() as session:
        dialog = await session.scalar(
            select(SupportDialog).where(
                SupportDialog.customer_telegram_id == message.from_user.id,
                SupportDialog.status == SupportDialogStatus.OPEN,
            )
        )
        if dialog is None:
            return
        copied = await bot.copy_message(
            chat_id=settings.owner_telegram_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            reply_markup=support_keyboard(str(dialog.id), message.from_user.id),
        )
        session.add(
            SupportForward(
                dialog_id=dialog.id,
                owner_message_id=copied.message_id,
                customer_message_id=message.message_id,
            )
        )
        await session.commit()
