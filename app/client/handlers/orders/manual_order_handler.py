import re
import time
from dataclasses import dataclass
from typing import Optional

from telebot import types

from app.client.bot.bot import bot
from app.client.handlers.user_context import get_telegram_services_or_notify
from app.client.handlers.utils.message_utils import last_messages, send_or_edit_message
from app.client.log.logger import setup_logger
from app.services.orders import (
    CONFIRM_TOKEN_TTL_SECONDS,
    OrderConfirmCommand,
    OrderExecutionBlocked,
    OrderExecutionResult,
    OrderPreviewRequest,
    OrderPreviewResult,
    OrderService,
    OrderServiceError,
)


logger = setup_logger(__name__)
order_service: Optional[OrderService] = None

MANUAL_ORDER_INPUT_RE = re.compile(r"^([A-Z0-9-]+)\s+([1-9][0-9]*)$")
MANUAL_TRADE_COMMAND_RE = re.compile(r"^\s*(buy|sell)\s+([A-Z0-9-]+)\s+([1-9][0-9]*)\s*$", re.IGNORECASE)
MANUAL_TRADE_PREFIX_RE = re.compile(r"^\s*(buy|sell)\b", re.IGNORECASE)
CONFIRM_ORDER_COMMAND_RE = re.compile(r"^\s*confirm_order\s+(\S+)(?:\s+([A-Z0-9-]+))?\s*$", re.IGNORECASE)
CANCEL_ORDER_COMMAND_RE = re.compile(r"^\s*cancel_order\s+(\S+)\s*$", re.IGNORECASE)

MANUAL_FLOW_EXIT_COMMANDS = {
    "cancel": "menu",
    "back": "menu",
    "menu": "menu",
    "отмена": "menu",
    "назад": "menu",
    "меню": "menu",
    "portfolio": "portfolio",
    "портфель": "portfolio",
    "help": "help",
    "помощь": "help",
}
MANUAL_FLOW_CALLBACKS = {
    "manual_cancel": "menu",
    "manual_menu": "menu",
    "manual_portfolio": "portfolio",
}


@dataclass(frozen=True)
class ManualTradeCommand:
    operation: str
    ticker: str
    quantity: int


@dataclass(frozen=True)
class ConfirmOrderCommand:
    confirm_token: str
    ticker_confirmation: Optional[str] = None


@dataclass(frozen=True)
class TelegramOrderPreview:
    chat_id: int
    operation: str
    ticker: str
    lots: int
    created_at: float
    user_id: str = ""


telegram_order_previews: dict[str, TelegramOrderPreview] = {}


def get_order_service_for_chat(chat_id: int) -> tuple[Optional[OrderService], str]:
    if order_service is not None:
        return order_service, "test"

    services = get_telegram_services_or_notify(chat_id)
    if services is None:
        return None, ""
    return services.order_service, services.user.user_id


def parse_manual_trade_command(text: Optional[str]) -> Optional[ManualTradeCommand]:
    if not text:
        return None

    match = MANUAL_TRADE_COMMAND_RE.match(text)
    if not match:
        return None

    operation, ticker, quantity_text = match.groups()
    return ManualTradeCommand(operation=operation.lower(), ticker=ticker.upper(), quantity=int(quantity_text))


def is_invalid_manual_trade_command(text: Optional[str]) -> bool:
    return bool(text and MANUAL_TRADE_PREFIX_RE.match(text) and parse_manual_trade_command(text) is None)


def parse_confirm_order_command(text: Optional[str]) -> Optional[ConfirmOrderCommand]:
    if not text:
        return None

    match = CONFIRM_ORDER_COMMAND_RE.match(text)
    if not match:
        return None

    confirm_token, ticker_confirmation = match.groups()
    return ConfirmOrderCommand(
        confirm_token=confirm_token.strip(),
        ticker_confirmation=ticker_confirmation.strip().upper() if ticker_confirmation else None,
    )


def parse_cancel_order_command(text: Optional[str]) -> Optional[str]:
    if not text:
        return None

    match = CANCEL_ORDER_COMMAND_RE.match(text)
    if not match:
        return None
    return match.group(1).strip()


def resolve_manual_flow_exit(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    return MANUAL_FLOW_EXIT_COMMANDS.get(text.strip().lower())


def build_manual_order_keyboard() -> types.InlineKeyboardMarkup:
    inline_keyboard = types.InlineKeyboardMarkup()
    inline_keyboard.add(types.InlineKeyboardButton(text="Cancel", callback_data="manual_cancel"))
    inline_keyboard.add(types.InlineKeyboardButton(text="Portfolio", callback_data="manual_portfolio"))
    inline_keyboard.add(types.InlineKeyboardButton(text="Menu", callback_data="manual_menu"))
    return inline_keyboard


def clear_manual_order_step(chat_id: int) -> None:
    clear_step = getattr(bot, "clear_step_handler_by_chat_id", None)
    if clear_step:
        clear_step(chat_id)


def handle_manual_flow_exit(chat_id: int, action: str, message=None) -> None:
    clear_manual_order_step(chat_id)

    if action == "portfolio":
        from app.client.handlers.portfolio.portfolio_handler import get_portfolio_handler

        if message is not None:
            get_portfolio_handler(message)
        else:
            send_or_edit_message(chat_id, "Order preview cancelled. Press `Portfolio` to open your portfolio.")
        return

    if action == "help":
        from app.client.handlers.help.help_handler import send_help

        send_help(chat_id)
        return

    send_or_edit_message(chat_id, "Order preview cancelled. Use `/start`, `Buy`, `Sell`, or `Portfolio` when ready.")


@bot.message_handler(func=lambda message: message.text == "Ручная заявка")
def manual_order_handler(message):
    chat_id = message.chat.id

    inline_keyboard = types.InlineKeyboardMarkup()
    inline_keyboard.add(types.InlineKeyboardButton(text="Buy", callback_data="manual_buy"))
    inline_keyboard.add(types.InlineKeyboardButton(text="Sell", callback_data="manual_sell"))

    msg = bot.send_message(
        chat_id=chat_id,
        text=(
            "*Manual order preview*\n\n"
            "Choose a side, then enter ticker and lots. Nothing is sent to the broker until you confirm."
        ),
        reply_markup=inline_keyboard,
        parse_mode="Markdown",
    )
    last_messages[chat_id] = msg.message_id


@bot.message_handler(func=lambda message: message.text == "Buy")
def manual_buy_handler(message):
    prompt_manual_order(message.chat.id, "buy")


@bot.message_handler(func=lambda message: message.text == "Sell")
def manual_sell_handler(message):
    prompt_manual_order(message.chat.id, "sell")


@bot.message_handler(func=lambda message: parse_manual_trade_command(getattr(message, "text", None)) is not None)
def manual_trade_command_handler(message):
    command = parse_manual_trade_command(message.text)
    if command is None:
        return

    preview_manual_order(message.chat.id, command.operation, command.ticker, command.quantity)


@bot.message_handler(func=lambda message: is_invalid_manual_trade_command(getattr(message, "text", None)))
def invalid_manual_trade_command_handler(message):
    send_invalid_manual_order_format(message.chat.id)


@bot.message_handler(func=lambda message: parse_confirm_order_command(getattr(message, "text", None)) is not None)
def confirm_order_command_handler(message):
    command = parse_confirm_order_command(message.text)
    if command is None:
        return
    confirm_manual_order(message.chat.id, command.confirm_token, command.ticker_confirmation)


@bot.message_handler(func=lambda message: parse_cancel_order_command(getattr(message, "text", None)) is not None)
def cancel_order_command_handler(message):
    confirm_token = parse_cancel_order_command(message.text)
    if confirm_token is None:
        return
    cancel_manual_order(message.chat.id, confirm_token)


@bot.callback_query_handler(func=lambda call: call.data in {"manual_buy", "manual_sell"})
def manual_order_side_handler(call):
    operation = "buy" if call.data == "manual_buy" else "sell"
    prompt_manual_order(call.message.chat.id, operation)


def prompt_manual_order(chat_id: int, operation: str):
    action = "buy" if operation == "buy" else "sell"
    msg = send_or_edit_message(
        chat_id,
        (
            f"*Manual {action} preview*\n\n"
            "Enter ticker and lots separated by a space.\n"
            "Example: `SBER 1`\n\n"
            "Nothing is sent to the broker until you confirm the preview.\n"
            "To exit, send `cancel`, `menu`, or `portfolio`."
        ),
        reply_markup=build_manual_order_keyboard(),
    )
    bot.register_next_step_handler(msg, process_manual_order, operation)


def process_manual_order(message, operation: str):
    chat_id = message.chat.id
    exit_action = resolve_manual_flow_exit(getattr(message, "text", None))
    if exit_action is not None:
        handle_manual_flow_exit(chat_id, exit_action, message)
        return

    message_text = getattr(message, "text", None)
    command = parse_manual_trade_command(message_text)
    if command is not None:
        preview_manual_order(chat_id, command.operation, command.ticker, command.quantity)
        return

    text = (message_text or "").strip().upper()
    match = MANUAL_ORDER_INPUT_RE.match(text)
    if not match:
        msg = send_or_edit_message(
            chat_id,
            (
                "*Invalid manual order format*\n\n"
                "Enter ticker and lots separated by a space.\n"
                "Example: `SBER 1`\n\n"
                "To exit, send `cancel`, `menu`, or `portfolio`."
            ),
            reply_markup=build_manual_order_keyboard(),
        )
        bot.register_next_step_handler(msg, process_manual_order, operation)
        return

    ticker, quantity_text = match.groups()
    preview_manual_order(chat_id, operation, ticker, int(quantity_text))


@bot.callback_query_handler(func=lambda call: call.data in MANUAL_FLOW_CALLBACKS)
def manual_order_exit_handler(call):
    chat_id = call.message.chat.id
    action = MANUAL_FLOW_CALLBACKS[call.data]
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    handle_manual_flow_exit(chat_id, action, call.message)


def preview_manual_order(chat_id: int, operation: str, ticker: str, lots: int) -> None:
    _cleanup_telegram_order_previews()
    selected_order_service, user_id = get_order_service_for_chat(chat_id)
    if selected_order_service is None:
        return

    logger.info(
        "Manual order preview requested: user_id=%s operation=%s ticker=%s lots=%s status=received",
        user_id,
        operation,
        ticker,
        lots,
    )

    try:
        preview = selected_order_service.preview(
            OrderPreviewRequest(
                operation=operation,
                ticker=ticker,
                lots=lots,
            )
        )
    except OrderServiceError as exc:
        logger.warning(
            "Manual order preview blocked: operation=%s ticker=%s lots=%s reason=%s",
            operation,
            ticker,
            lots,
            str(exc),
        )
        send_or_edit_message(chat_id, f"*Order preview cannot continue*\n\n{str(exc)}")
        return

    telegram_order_previews[preview.confirm_token] = TelegramOrderPreview(
        chat_id=chat_id,
        user_id=user_id,
        operation=preview.operation,
        ticker=preview.ticker,
        lots=preview.lots,
        created_at=time.time(),
    )
    send_or_edit_message(chat_id, format_order_preview(preview))


def confirm_manual_order(chat_id: int, confirm_token: str, ticker_confirmation: Optional[str] = None) -> None:
    _cleanup_telegram_order_previews()
    selected_order_service, user_id = get_order_service_for_chat(chat_id)
    if selected_order_service is None:
        return

    preview = telegram_order_previews.get(confirm_token)
    if preview is None:
        send_or_edit_message(chat_id, "Order preview was not found or has expired. Create a new preview.")
        return
    if preview.chat_id != chat_id:
        send_or_edit_message(chat_id, "This order preview belongs to another chat and cannot be confirmed here.")
        return
    if preview.user_id and preview.user_id != user_id:
        send_or_edit_message(chat_id, "This order preview belongs to another user and cannot be confirmed here.")
        return

    try:
        result = selected_order_service.execute(
            OrderConfirmCommand(
                operation=preview.operation,
                ticker=preview.ticker,
                lots=preview.lots,
                confirm_token=confirm_token,
                ticker_confirmation=ticker_confirmation,
            )
        )
    except OrderExecutionBlocked as exc:
        telegram_order_previews.pop(confirm_token, None)
        logger.warning(
            "Manual order execution blocked: operation=%s ticker=%s lots=%s reason=%s",
            preview.operation,
            preview.ticker,
            preview.lots,
            str(exc),
        )
        send_or_edit_message(chat_id, f"*Order was not sent*\n\n{str(exc)}\n\nCreate a new preview to try again.")
        return
    except OrderServiceError as exc:
        telegram_order_previews.pop(confirm_token, None)
        logger.error(
            "Manual order execution failed: operation=%s ticker=%s lots=%s error=%s",
            preview.operation,
            preview.ticker,
            preview.lots,
            str(exc),
        )
        send_or_edit_message(chat_id, f"*Order was not sent*\n\n{str(exc)}\n\nCreate a new preview to try again.")
        return

    telegram_order_previews.pop(confirm_token, None)
    logger.info(
        "Manual order submitted through OrderService: operation=%s ticker=%s lots=%s order_id=%s",
        result.operation,
        result.ticker,
        result.lots,
        result.order_id,
    )
    send_or_edit_message(chat_id, format_order_result(result))


def cancel_manual_order(chat_id: int, confirm_token: str) -> None:
    _cleanup_telegram_order_previews()
    selected_order_service, user_id = get_order_service_for_chat(chat_id)
    if selected_order_service is None:
        return

    preview = telegram_order_previews.get(confirm_token)
    if preview is None:
        send_or_edit_message(chat_id, "Order preview was not found or has already expired.")
        return
    if preview.chat_id != chat_id:
        send_or_edit_message(chat_id, "This order preview belongs to another chat and cannot be cancelled here.")
        return
    if preview.user_id and preview.user_id != user_id:
        send_or_edit_message(chat_id, "This order preview belongs to another user and cannot be cancelled here.")
        return

    telegram_order_previews.pop(confirm_token, None)
    selected_order_service.cancel_preview(confirm_token)
    send_or_edit_message(chat_id, f"Order preview for `{preview.ticker}` was cancelled. No broker order was sent.")


def format_order_preview(preview: OrderPreviewResult) -> str:
    lines = [
        "*Order preview*",
        "",
        f"Side: `{preview.operation.upper()}`",
        f"Ticker: `{preview.ticker}`",
        f"Lots: `{preview.lots}`",
        f"Estimated price: `{preview.estimated_price_display}`",
        f"Estimated amount: `{preview.estimated_value_display}`",
        f"Mode: `{preview.mode.banner_title}`",
        f"Trading: `{'enabled' if preview.trading_enabled else 'disabled'}`",
    ]

    if preview.warnings:
        lines.append("")
        lines.append("*Warnings*")
        lines.extend(f"- {warning}" for warning in preview.warnings)

    lines.append("")
    lines.append("No broker order has been sent yet.")
    if preview.can_execute:
        if preview.requires_ticker_confirmation:
            lines.append(f"Confirm: `confirm_order {preview.confirm_token} {preview.ticker}`")
        else:
            lines.append(f"Confirm: `confirm_order {preview.confirm_token}`")
    else:
        lines.append("Execution is blocked in the current mode.")
    lines.append(f"Cancel: `cancel_order {preview.confirm_token}`")
    return "\n".join(lines)


def format_order_result(result: OrderExecutionResult) -> str:
    return "\n".join(
        [
            "*Order submitted*",
            "",
            result.message,
            "",
            f"Mode: `{result.mode.banner_title}`",
            f"Side: `{result.operation.upper()}`",
            f"Ticker: `{result.ticker}`",
            f"Lots: `{result.lots}`",
            f"Executed price: `{result.executed_price_display}`",
            f"Total value: `{result.total_value_display}`",
            f"Order ID: `{result.order_id}`",
        ]
    )


def send_invalid_manual_order_format(chat_id: int) -> None:
    send_or_edit_message(
        chat_id,
        (
            "*Invalid manual order format*\n\n"
            "Use `buy SBER 1`, `sell SBER 1`, or enter `SBER 1` after choosing Buy/Sell."
        ),
    )


def _cleanup_telegram_order_previews() -> None:
    cutoff = time.time() - CONFIRM_TOKEN_TTL_SECONDS
    for confirm_token, preview in list(telegram_order_previews.items()):
        if preview.created_at < cutoff:
            telegram_order_previews.pop(confirm_token, None)
