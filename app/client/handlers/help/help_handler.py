from telebot import types

from app.client.bot.bot import bot
from app.client.config import get_investor_reminder_time, investor_reminders_enabled
from app.client.handlers.utils.message_utils import last_messages


HELP_TEXT = (
    "*Investor mode help*\n\n"
    "Main actions:\n"
    "- `Portfolio` - current positions\n"
    "- `Buy` - enter a manual buy order\n"
    "- `Sell` - enter a manual sell order\n"
    "- `Dividends` - check dividend information for your watchlist\n"
    "- `Watchlist` - add or remove tickers to follow\n"
    "- `Stats` - basic text statistics for manual trades\n"
    "- `Reports` - simple reminder/report setup notes\n\n"
    "Direct commands:\n"
    "- `buy SBER 1` - create a preview\n"
    "- `sell SBER 1` - create a preview\n"
    "- `confirm_order <token>` - confirm a sandbox preview\n"
    "- `confirm_order <token> SBER` - confirm a production preview\n"
    "- `cancel_order <token>` - cancel a preview\n\n"
    "Sandbox mode is the default. No signals, ML, GPT/LSTM, or auto-trading are active in investor v1."
)


def send_help(chat_id):
    inline_keyboard = types.InlineKeyboardMarkup()
    inline_keyboard.add(types.InlineKeyboardButton(text="Reports", callback_data="investor_reports"))
    inline_keyboard.add(types.InlineKeyboardButton(text="Sandbox info", callback_data="sandbox_info"))

    msg = bot.send_message(
        chat_id=chat_id,
        text=HELP_TEXT,
        reply_markup=inline_keyboard,
        parse_mode="Markdown",
    )
    last_messages[chat_id] = msg.message_id


@bot.message_handler(commands=["help"])
def help_command_handler(message):
    send_help(message.chat.id)


@bot.message_handler(func=lambda message: message.text == "Help")
def help_handler(message):
    send_help(message.chat.id)


def send_reports_help(chat_id):
    status = "enabled" if investor_reminders_enabled() else "disabled"
    reminder_time = get_investor_reminder_time()
    text = (
        "*Reports and reminders*\n\n"
        "Investor v1 keeps this intentionally simple:\n"
        "- use `Portfolio` for current positions;\n"
        "- use `Dividends` for dividend checks;\n"
        "- use `Stats` for manual-trade statistics;\n"
        "- optional daily check-in reminders do not contain signals or trade advice.\n\n"
        f"Reminder status: `{status}`\n"
        f"Reminder time: `{reminder_time}` Europe/Moscow\n\n"
        "To enable reminders, set `ENABLE_INVESTOR_REMINDERS=true` and optionally "
        "`INVESTOR_REMINDER_TIME=09:00`, then restart the app."
    )
    msg = bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
    last_messages[chat_id] = msg.message_id


@bot.message_handler(func=lambda message: message.text == "Reports")
def reports_handler(message):
    send_reports_help(message.chat.id)


@bot.callback_query_handler(func=lambda call: call.data == "investor_reports")
def reports_callback_handler(call):
    send_reports_help(call.message.chat.id)
