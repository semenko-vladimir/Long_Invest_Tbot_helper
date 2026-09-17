from telebot import types

from app.client.bot.bot import bot
from app.client.handlers.utils.message_utils import last_messages
from app.services.mode import ModeContext, ModeService


TRADING_MAIN_MENU_BUTTONS = (
    ("Portfolio", "Buy"),
    ("Sell", "Dividends"),
    ("Watchlist", "Stats"),
    ("Reports", "Help"),
)

READ_ONLY_MAIN_MENU_BUTTONS = (
    ("Portfolio", "Dividends"),
    ("Watchlist", "Stats"),
    ("Reports", "Help"),
)


def build_main_menu(mode: ModeContext | None = None) -> types.ReplyKeyboardMarkup:
    mode = mode or ModeService().current()
    buttons = TRADING_MAIN_MENU_BUTTONS if mode.trading_available else READ_ONLY_MAIN_MENU_BUTTONS
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for row in buttons:
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
