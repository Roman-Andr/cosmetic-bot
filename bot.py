import asyncio
import json
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import gspread
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from prometheus_client import start_http_server, Counter, Gauge

from config import API_TOKEN, ADMIN_ID, GOOGLE_SHEET_NAME, GOOGLE_SHEETS_CREDENTIALS_FILE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        TimedRotatingFileHandler("bot.log", when="midnight", interval=1, backupCount=31),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Metrics
REQUESTS = Counter('bot_requests_total', 'Total number of requests')
ACTIVE_DIALOGS = Gauge('bot_active_dialogs', 'Number of active dialogs')
BLOCKED_USERS = Gauge('bot_blocked_users', 'Number of blocked users')

# Bot and dispatcher initialization
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Constants for data files
DATA_FILE = Path("bot_data.json")

# Initialize Google Sheets client
gc = gspread.service_account(filename=GOOGLE_SHEETS_CREDENTIALS_FILE)
sh = gc.open(GOOGLE_SHEET_NAME)
worksheet = sh.sheet1

# Cache for Google Sheets data
cached_products = []


async def cache_products():
    """Cache products from Google Sheets periodically."""
    global cached_products
    while True:
        try:
            records = worksheet.get_all_records()
            cached_products = records
            logger.info("Products data cached successfully.")
        except Exception as e:
            logger.error(f"Error caching products from Google Sheets: {e}")
        await asyncio.sleep(3600)  # Cache every hour


def read_product_from_cache(product_id):
    """Read product data from cache by ID."""
    for row in cached_products:
        if row.get("Tilda UID") == int(product_id):
            return row
    return None


def load_data():
    """Load data from JSON file."""
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading data from {DATA_FILE}: {e}")
    return {"active_dialogs": {}, "blocked_users": [], "dialog_messages": {}}


def save_data(data):
    """Save data to JSON file."""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving data to {DATA_FILE}: {e}")


def get_active_dialogs():
    """Get active dialogs as a dictionary {user_id: product_id}."""
    return load_data().get("active_dialogs", {})


def get_blocked_users():
    """Get set of blocked users."""
    return set(load_data()["blocked_users"])


def get_dialog_messages(user_id):
    """Get list of messages for a specific user."""
    return load_data()["dialog_messages"].get(str(user_id), [])


def add_active_dialog(user_id, product_id):
    """Add user with product_id to active dialogs."""
    data = load_data()

    if user_id not in data["active_dialogs"].keys():
        ACTIVE_DIALOGS.inc()

    data["active_dialogs"][str(user_id)] = product_id  # Сохраняем user_id: product_id
    save_data(data)
    logger.info(f"Added active dialog: user ID {user_id}, product ID {product_id}")


def remove_active_dialog(user_id):
    """Remove user from active dialogs."""
    data = load_data()
    if str(user_id) in data["active_dialogs"].keys():
        print("User removed from active dialogs.")
        ACTIVE_DIALOGS.dec()
        del data["active_dialogs"][str(user_id)]
        save_data(data)
        logger.info(f"Removed active dialog with user ID: {user_id}")


def add_blocked_user(user_id):
    """Add user to blocked list."""
    data = load_data()
    if user_id not in data["blocked_users"]:
        BLOCKED_USERS.inc()
        data["blocked_users"].append(user_id)
        save_data(data)
        logger.info(f"User ID: {user_id} has been blocked")


def remove_blocked_user(user_id):
    """Remove user from blocked list."""
    data = load_data()
    if user_id in data["blocked_users"]:
        BLOCKED_USERS.dec()
        data["blocked_users"].remove(user_id)
        save_data(data)
        logger.info(f"User ID: {user_id} has been unblocked")


def add_dialog_message(user_id, message_id):
    """Add message ID to user's dialog messages."""
    data = load_data()
    if str(user_id) not in data["dialog_messages"]:
        data["dialog_messages"][str(user_id)] = []
    if message_id not in data["dialog_messages"][str(user_id)]:
        data["dialog_messages"][str(user_id)].append(message_id)
        save_data(data)
        logger.info(f"Added message ID: {message_id} to dialog with user ID: {user_id}")


def remove_dialog_messages(user_id):
    """Remove all messages for a specific user."""
    data = load_data()
    if str(user_id) in data["dialog_messages"]:
        del data["dialog_messages"][str(user_id)]
        save_data(data)
        logger.info(f"Removed all messages from dialog with user ID: {user_id}")


@dp.message(Command("start"))
async def start(message: Message):
    """Handle /start command and show product info."""
    REQUESTS.inc()

    args = message.text.split(" ")
    product_id = args[1] if len(args) > 1 else None

    if not product_id:
        logger.warning("No product ID provided.")
        return

    product = read_product_from_cache(product_id)
    if not product:
        logger.warning(f"Product with ID {product_id} not found.")
        return

    greeting = "Приветствуем вас! Спасибо за ваш интерес!"
    product_name = product["Title"]
    product_price = f"Стоимость: {product["Price"]}"
    text = f"{greeting}\n\n{product_name}\n\n{product_price}\n\nХотите оформить заказ?"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить в корзину", url=product["Url"])],
        [InlineKeyboardButton(text="Нужна помощь", callback_data=f"need_help_{product_id}")]
    ])
    photo_url = product["Photo"]
    await message.answer_photo(photo_url, caption=text, reply_markup=keyboard, parse_mode="HTML")
    logger.info(
        f"Showed product {product_name} to user ID: {message.from_user.id}, Name: {message.from_user.full_name}")


@dp.callback_query(lambda c: c.data.startswith("need_help_"))
async def need_help(callback_query: CallbackQuery):
    """Handle help request from user."""
    user_id = callback_query.from_user.id
    user_name = callback_query.from_user.full_name
    product_id = callback_query.data.replace("need_help_", "")

    if user_id in get_blocked_users() or user_id == ADMIN_ID:
        logger.warning(f"User {user_name} ({user_id}) tried to request help but was blocked or already in a dialog.")
        return

    await callback_query.answer("Задавайте свои вопросы.")
    await bot.send_message(user_id, "Задавайте свои вопросы")

    if user_id != ADMIN_ID:
        add_active_dialog(user_id, product_id)

    logger.info(f"User {user_name} ({user_id}) requested help. Product ID: {product_id}")


@dp.message(lambda message: str(message.from_user.id) in get_active_dialogs().keys() and (
        message.photo or not message.text.startswith("/")))
async def forward_to_admin(message: Message):
    """Forward user message (text, photo, document, etc.) to admin."""
    user_id = message.from_user.id
    user_name = message.from_user.full_name
    active_dialogs = get_active_dialogs()
    product_id = active_dialogs.get(str(user_id), "Неизвестно")  # Получаем product_id, если есть

    if user_id in get_blocked_users():
        logger.warning(f"User ID: {user_id}, Name: {user_name} tried to send a message but was blocked.")
        return

    # Формируем сообщение для админа с product_id
    admin_message = f"Сообщение от {user_name} (ID: {user_id})\nID продукта: {product_id}\n\n"

    if message.text:
        admin_message += f"{message.text}"
        sent_message = await bot.send_message(
            ADMIN_ID,
            admin_message,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Закончить", callback_data=f"end_dialog_{user_id}")],
                [InlineKeyboardButton(text="Заблокировать", callback_data=f"block_user_{user_id}")],
                [InlineKeyboardButton(text="Разблокировать", callback_data=f"unblock_user_{user_id}")]
            ])
        )
        add_dialog_message(user_id, sent_message.message_id)
        logger.info(
            f"Text message from user ID: {user_id}, Name: {user_name}, Product ID: {product_id} forwarded to admin.")

    elif message.photo:
        photo = message.photo[-1]  # Get the highest resolution photo
        caption = admin_message + (message.caption if message.caption else "")
        sent_message = await bot.send_photo(
            ADMIN_ID,
            photo.file_id,
            caption=caption,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Закончить", callback_data=f"end_dialog_{user_id}")],
                [InlineKeyboardButton(text="Заблокировать", callback_data=f"block_user_{user_id}")],
                [InlineKeyboardButton(text="Разблокировать", callback_data=f"unblock_user_{user_id}")]
            ])
        )
        add_dialog_message(user_id, sent_message.message_id)
        logger.info(f"Photo from user ID: {user_id}, Name: {user_name}, Product ID: {product_id} forwarded to admin.")

    elif message.document:
        caption = admin_message + (message.caption if message.caption else "")
        sent_message = await bot.send_document(
            ADMIN_ID,
            message.document.file_id,
            caption=caption,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Закончить", callback_data=f"end_dialog_{user_id}")],
                [InlineKeyboardButton(text="Заблокировать", callback_data=f"block_user_{user_id}")],
                [InlineKeyboardButton(text="Разблокировать", callback_data=f"unblock_user_{user_id}")]
            ])
        )
        add_dialog_message(user_id, sent_message.message_id)
        logger.info(
            f"Document from user ID: {user_id}, Name: {user_name}, Product ID: {product_id} forwarded to admin.")

    else:
        await bot.send_message(ADMIN_ID,
                               f"Пользователь {user_name} (ID: {user_id}) отправил неподдерживаемый тип медиа.\nПродукт ID: {product_id}")
        logger.warning(f"Unsupported media type from user ID: {user_id}, Name: {user_name}, Product ID: {product_id}.")


@dp.message(lambda message: message.from_user.id == ADMIN_ID and message.reply_to_message)
async def admin_reply(message: Message):
    """Handle admin reply to user message."""
    replied_message = message.reply_to_message.text
    user_id = int(replied_message.split("(ID: ")[1].split(")")[0])
    user_name = replied_message.split("Сообщение от ")[1].split(" (ID:")[0]
    add_dialog_message(user_id, message.message_id)
    await bot.send_message(user_id, message.text)
    logger.info(f"Admin replied to message from user ID: {user_id}, Name: {user_name}.")


@dp.callback_query(lambda c: c.data.startswith("end_dialog_"))
async def end_dialog(callback_query: CallbackQuery):
    """End dialog with user."""
    user_id = int(callback_query.data.split("_")[2])
    user_name = (await bot.get_chat(user_id)).first_name

    dialog_messages = get_dialog_messages(user_id)
    if dialog_messages:
        for message_id in dialog_messages:
            try:
                await bot.delete_message(ADMIN_ID, message_id)
            except Exception as e:
                logger.error(f"Failed to delete message {message_id}: {e}")

        remove_dialog_messages(user_id)

    await callback_query.answer(f"Диалог с пользователем {user_name} завершен.")
    if str(user_id) in get_active_dialogs().keys():
        remove_active_dialog(user_id)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Нужна помощь", callback_data="need_help")]
    ])
    await bot.send_message(user_id, "Если у вас есть еще вопросы, нажмите 'Нужна помощь'.", reply_markup=keyboard)
    logger.info(f"Dialog with user ID: {user_id}, Name: {user_name} has ended.")


@dp.callback_query(lambda c: c.data.startswith("block_user_"))
async def block_user(callback_query: CallbackQuery):
    """Block user."""
    user_id = int(callback_query.data.split("_")[2])
    user_name = (await bot.get_chat(user_id)).first_name
    await callback_query.answer(f"Пользователь {user_name} заблокирован.")
    add_blocked_user(user_id)
    if str(user_id) in get_active_dialogs().keys():
        remove_active_dialog(user_id)
    logger.info(f"User ID: {user_id}, Name: {user_name} has been blocked.")


@dp.callback_query(lambda c: c.data.startswith("unblock_user_"))
async def unblock_user(callback_query: CallbackQuery):
    """Unblock user."""
    user_id = int(callback_query.data.split("_")[2])
    user_name = (await bot.get_chat(user_id)).first_name
    if user_id in get_blocked_users():
        remove_blocked_user(user_id)
        await callback_query.answer(f"Пользователь {user_name} разблокирован.")
        logger.info(f"User ID: {user_id}, Name: {user_name} has been unblocked.")
    else:
        await callback_query.answer(f"Пользователь {user_name} не был заблокирован.")
        logger.warning(f"Attempt to unblock user ID: {user_id}, Name: {user_name}, who was not blocked.")


async def main():
    """Start the bot."""
    logger.info("Bot started.")
    asyncio.create_task(cache_products())  # Start the caching task
    await dp.start_polling(bot)


if __name__ == "__main__":
    start_http_server(8000)
    asyncio.run(main())
