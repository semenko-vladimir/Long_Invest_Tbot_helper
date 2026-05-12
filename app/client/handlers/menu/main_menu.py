from telebot import types

from app.client.bot.bot import bot
from app.client.handlers.utils.message_utils import last_messages


MAIN_MENU_BUTTONS = (
    ("Portfolio", "Buy"),
    ("Sell", "Dividends"),
    ("Watchlist", "Stats"),
    ("Reports", "Help"),
)


def build_main_menu() -> types.ReplyKeyboardMarkup:
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for row in MAIN_MENU_BUTTONS:
        keyboard.row(*(types.KeyboardButton(label) for label in row))
    return keyboard


def send_main_menu(chat_id: int, text: str = "Investor mode is ready.") -> None:
    msg = bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=build_main_menu(),
        parse_mode="Markdown",
    )
    last_messages[chat_id] = msg.message_id
