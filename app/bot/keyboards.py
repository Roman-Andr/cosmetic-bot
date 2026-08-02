"""Reusable Telegram keyboards without business logic."""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)


def loyalty_web_app_keyboard(url: str) -> InlineKeyboardMarkup:
    """Open the Mini App from a bot message."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть программу лояльности", web_app=WebAppInfo(url=url))]
        ]
    )


def customer_menu() -> ReplyKeyboardMarkup:
    """Persistent customer action menu with a bot-level code fallback."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Получить код"), KeyboardButton(text="Программа лояльности")]
        ],
        resize_keyboard=True,
    )


def support_keyboard(
    dialog_id: str,
    customer_telegram_id: int,
    *,
    is_blocked: bool = False,
) -> InlineKeyboardMarkup:
    """Owner controls attached to each forwarded support message."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Закончить диалог", callback_data=f"support:end:{dialog_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Разблокировать" if is_blocked else "Заблокировать",
                    callback_data=(
                        f"support:unblock:{dialog_id}:{customer_telegram_id}"
                        if is_blocked
                        else f"support:block:{dialog_id}:{customer_telegram_id}"
                    ),
                )
            ],
        ]
    )


def sale_product_keyboard(product_ids: list[str]) -> InlineKeyboardMarkup:
    """Allow an administrator to finish or skip optional product selection."""
    label = "Выбрать товары позже" if not product_ids else f"Готово ({len(product_ids)})"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data="sale:finish")],
            [InlineKeyboardButton(text="Без товаров", callback_data="sale:skip")],
            [InlineKeyboardButton(text="Отменить", callback_data="sale:cancel")],
        ]
    )


def sale_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Require an explicit irreversible sale confirmation."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Подтвердить продажу", callback_data="sale:confirm")],
            [InlineKeyboardButton(text="Отменить", callback_data="sale:cancel")],
        ]
    )


def owner_menu(url: str) -> InlineKeyboardMarkup:
    """Quick links for owner-only statistics and configuration."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Статистика", callback_data="owner:stats")],
            [InlineKeyboardButton(text="Добавить администратора", callback_data="owner:add-sales")],
            [InlineKeyboardButton(text="Настроить уровни", callback_data="owner:tiers")],
            [InlineKeyboardButton(text="Кабинет и выгрузки", web_app=WebAppInfo(url=url))],
        ]
    )
