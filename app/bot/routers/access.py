"""Shared authorization and support access checks for Telegram handlers."""

from aiogram.types import Message

from app.db.session import SessionLocal
from app.models import AdminRole, AdminUser, BlockedUser


async def get_admin_role(telegram_user_id: int) -> AdminRole | None:
    """Load a current active administrator role."""
    async with SessionLocal() as session:
        admin = await session.get(AdminUser, telegram_user_id)
        if admin is None or not admin.is_active:
            return None
        return admin.role


async def is_blocked(telegram_user_id: int) -> bool:
    """Check the persistent owner-managed support blocklist."""
    async with SessionLocal() as session:
        return await session.get(BlockedUser, telegram_user_id) is not None


async def require_sales(message: Message) -> bool:
    """Reject a command unless the sender is an active sales user or owner."""
    if message.from_user is None or await get_admin_role(message.from_user.id) is None:
        await message.answer("Эта команда доступна только администраторам продаж.")
        return False
    return True


async def require_owner_message(message: Message) -> bool:
    """Reject a command unless the sender is the configured owner."""
    if (
        message.from_user is None
        or await get_admin_role(message.from_user.id) is not AdminRole.OWNER
    ):
        await message.answer("Эта команда доступна только главному администратору.")
        return False
    return True
