from typing import Optional

from telebot import types

from app.client.bot.bot import bot
from app.client.handlers.user_context import get_telegram_services_or_notify
from app.services.plan_confirmation import PlanConfirmationService
from app.services.strategy_confirmation import StrategyConfirmationService
from app.services.strategy_models import (
    STRATEGY_STATUS_BLOCKED,
    STRATEGY_STATUS_EXECUTED,
    STRATEGY_STATUS_FAILED,
    STRATEGY_STATUS_SKIPPED,
)

plan_confirmation_service: Optional[PlanConfirmationService] = None
strategy_confirmation_service: Optional[StrategyConfirmationService] = None


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


def send_strategy_confirmation_message(
    chat_id: int,
    *,
    token: str,
    strategy_id: str,
    strategy_name: str,
    operation: str,
    ticker: str,
    lots: int,
    estimated_value_display: str,
    reason: str,
    mode_title: str,
) -> None:
    """Sends a Telegram proposal that still requires explicit order confirmation."""
    op_label = "ПОКУПКА" if operation == "buy" else "ПРОДАЖА"
    text = (
        f"Стратегия сработала: {strategy_name}\n"
        f"Strategy ID: {strategy_id}\n\n"
        f"Предложение: {op_label} {ticker}\n"
        f"Лоты: {lots}\n"
        f"Оценка: {estimated_value_display}\n"
        f"Причина: {reason}\n"
        f"Режим: {mode_title}\n\n"
        f"Брокерский ордер еще не отправлен.\n"
        f"Подтверди в течение 30 минут."
    )

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("Исполнить", callback_data=f"strategy_confirm:{token}"),
        types.InlineKeyboardButton("Пропустить", callback_data=f"strategy_skip:{token}"),
    )
    bot.send_message(chat_id, text, reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: call.data.startswith("plan_confirm:"))
def handle_plan_confirm(call) -> None:
    token = call.data.split(":", 1)[1]
    chat_id = call.message.chat.id
    if plan_confirmation_service and plan_confirmation_service.confirm(token, chat_id=chat_id):
        bot.answer_callback_query(call.id, "✅ Ордер отправлен!")
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
    else:
        bot.answer_callback_query(call.id, "⚠️ Запрос устарел или уже обработан.")


@bot.callback_query_handler(func=lambda call: call.data.startswith("strategy_confirm:"))
def handle_strategy_confirm(call) -> None:
    token = call.data.split(":", 1)[1]
    chat_id = call.message.chat.id
    if not strategy_confirmation_service:
        bot.answer_callback_query(call.id, "⚠️ Подтверждение стратегий сейчас недоступно.")
        return

    services = get_telegram_services_or_notify(chat_id)
    if services is None:
        bot.answer_callback_query(call.id, "⚠️ Чат не авторизован.")
        return

    result = strategy_confirmation_service.confirm(
        chat_id=chat_id,
        token=token,
        order_service=services.order_service,
    )
    if result.status == STRATEGY_STATUS_EXECUTED:
        bot.answer_callback_query(call.id, "✅ Ордер отправлен!")
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
        bot.send_message(chat_id, f"✅ Стратегия {result.strategy_name}: ордер {result.order_id or ''} отправлен.")
    elif result.status in {STRATEGY_STATUS_BLOCKED, STRATEGY_STATUS_FAILED}:
        bot.answer_callback_query(call.id, "❌ Ордер не отправлен.")
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
        bot.send_message(chat_id, f"❌ Стратегия {result.strategy_name}: {result.message}")
    else:
        bot.answer_callback_query(call.id, "⚠️ Запрос устарел или уже обработан.")


@bot.callback_query_handler(func=lambda call: call.data.startswith("strategy_skip:"))
def handle_strategy_skip(call) -> None:
    token = call.data.split(":", 1)[1]
    chat_id = call.message.chat.id
    if not strategy_confirmation_service:
        bot.answer_callback_query(call.id, "⚠️ Подтверждение стратегий сейчас недоступно.")
        return

    result = strategy_confirmation_service.skip(chat_id=chat_id, token=token, reason="user_declined")
    if result.status == STRATEGY_STATUS_SKIPPED:
        bot.answer_callback_query(call.id, "❌ Пропущено.")
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
