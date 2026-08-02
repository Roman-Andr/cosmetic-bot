"""Composition root for domain-specific Telegram update routers."""

from aiogram import Router

from app.bot.routers import customer, owner, sales, support

router = Router(name="customer-and-admin-workflows")
router.include_routers(
    customer.router,
    sales.router,
    owner.router,
    support.router,
)
