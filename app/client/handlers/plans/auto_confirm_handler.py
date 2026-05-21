from typing import Optional

from telebot import types

from app.client.bot.bot import bot
from app.services.plan_confirmation import PlanConfirmationService

plan_confirmation_service: Optional[PlanConfirmationService] = None


def send_plan_confirmation_message(
    chat_id: int,
    *,
    token: str,
    ticker: str,
    operation: str,
    lots: int,
    current_price: float,
    price_reason: str,
) -> None:
    """Sends a Telegram message with ✅/❌ inline buttons for plan confirmation."""
    op_label = "ПОКУПКА" if operation == "buy" else "ПРОДАЖА"
    text = (
        f"📋 *Авто-план готов к исполнению*\n\n"
        f"*{op_label}* {ticker} — {lots} лот(ов)\n"
        f"Цена: ~{current_price:.2f} ₽\n"
        f"Условие: {price_reason}\n\n"
        f"⏳ Подтверди в течение 30 минут."
    )

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("✅ Исполнить", callback_data=f"plan_confirm:{token}"),
        types.InlineKeyboardButton("❌ Пропустить", callback_data=f"plan_skip:{token}"),
    )
    bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode="Markdown")


def send_anti_greedy_confirmation_message(
    chat_id: int,
    *,
    token: str,
    ticker: str,
    operation: str,
    lots: int,
    current_price: float,
    price_reason: str,
) -> None:
    """Sends a Telegram message with inline buttons for anti-greedy sell confirmation."""
    op_label = "ПРОДАЖА" if operation == "sell" else operation.upper()
    text = (
        f"📋 *Anti-greedy предложение*\n\n"
        f"*{op_label}* {ticker} — {lots} лот(ов)\n"
        f"Цена: ~{current_price:.2f} ₽\n"
        f"Условие: {price_reason}\n\n"
        f"⏳ Подтверди в течение 30 минут."
    )

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("✅ Исполнить", callback_data=f"plan_confirm:{token}"),
        types.InlineKeyboardButton("❌ Пропустить", callback_data=f"plan_skip:{token}"),
    )
    bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data.startswith("plan_confirm:"))
def handle_plan_confirm(call) -> None:
    token = call.data.split(":", 1)[1]
    chat_id = call.message.chat.id
    if plan_confirmation_service and plan_confirmation_service.confirm(token, chat_id=chat_id):
        bot.answer_callback_query(call.id, "✅ Ордер отправлен!")
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
    else:
        bot.answer_callback_query(call.id, "⚠️ Запрос устарел или уже обработан.")


@bot.callback_query_handler(func=lambda call: call.data.startswith("plan_skip:"))
def handle_plan_skip(call) -> None:
    token = call.data.split(":", 1)[1]
    chat_id = call.message.chat.id
    if plan_confirmation_service and plan_confirmation_service.skip(
        token, "user_declined", chat_id=chat_id
    ):
        bot.answer_callback_query(call.id, "❌ Пропущено.")
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
    else:
        bot.answer_callback_query(call.id, "⚠️ Запрос устарел или уже обработан.")
