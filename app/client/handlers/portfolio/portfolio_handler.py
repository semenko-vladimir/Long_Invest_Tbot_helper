from telebot import types

from app.client.bot.bot import bot
from app.client.handlers.user_context import get_telegram_services_or_notify
from app.services.accounts import UnknownInvestmentAccountError
from app.services.portfolio import AccountPortfolioView, AggregatePortfolioView


PORTFOLIO_ROOT_CALLBACK = "portfolio:root"
PORTFOLIO_ACCOUNT_PREFIX = "portfolio:account:"


def build_aggregate_portfolio_message(portfolio: AggregatePortfolioView, user_name: str) -> str:
    lines = [
        "💼 *PORTFOLIO*",
        f"ℹ️ User: {user_name}",
        f"ℹ️ Mode: {portfolio.mode.mode}",
        f"💎 *Combined total: {portfolio.total_value_display}*",
    ]
    if portfolio.partial:
        lines.extend(["", "⚠️ *Partial data:* one or more accounts could not be loaded."])
    if portfolio.error:
        lines.extend(["", f"❌ {portfolio.error}"])
    if portfolio.accounts:
        lines.extend(["", "*Accounts*"])
    for account_view in portfolio.accounts:
        account = account_view.account
        type_label = f" · {_format_account_type(account.account_type)}" if account.account_type else ""
        if account_view.error:
            lines.append(f"⚠️ {account.account_name}{type_label}: unavailable")
        else:
            lines.append(f"• {account.account_name}{type_label}: {account_view.total_value_display}")
    return "\n".join(lines)


def build_aggregate_portfolio_keyboard(portfolio: AggregatePortfolioView) -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup()
    for account_view in portfolio.accounts:
        account = account_view.account
        keyboard.add(
            types.InlineKeyboardButton(
                text=account.account_name,
                callback_data=f"{PORTFOLIO_ACCOUNT_PREFIX}{account.investment_account_id}",
            )
        )
    return keyboard


def build_account_portfolio_message(portfolio: AccountPortfolioView) -> str:
    account = portfolio.account
    lines = [f"💼 *{account.account_name}*"]
    if account.account_type:
        lines.append(f"📋 Type: {_format_account_type(account.account_type)}")

    strategy = account.strategy
    if strategy is None or not any((strategy.title, strategy.thesis, strategy.strategy_key)):
        lines.append("🧭 Strategy: not configured")
    else:
        lines.append(f"🧭 Strategy: {strategy.title or strategy.strategy_key or 'Configured'}")
        if strategy.thesis:
            lines.append(strategy.thesis)

    if portfolio.error:
        lines.extend(["", f"❌ {portfolio.error}"])
        return "\n".join(lines)

    lines.extend(["", f"💎 *Total: {portfolio.total_value_display}*"])
    if portfolio.empty:
        lines.extend(["", "⚠️ This account has no positions."])
        return "\n".join(lines)

    lines.extend(["", "*Positions*"])
    for position in portfolio.positions:
        lines.extend(
            [
                "",
                f"🔖 *{position.ticker}* — {position.name}",
                f"├─ Quantity: {position.quantity_display}",
                f"├─ Average: {position.average_price_display}",
                f"├─ Current: {position.current_price_display}",
                f"└─ P/L: {position.pnl_display} ({position.return_display})",
            ]
        )
    return "\n".join(lines)


def build_account_portfolio_keyboard() -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="← All accounts", callback_data=PORTFOLIO_ROOT_CALLBACK))
    return keyboard


def send_aggregate_portfolio(chat_id: int) -> None:
    services = get_telegram_services_or_notify(chat_id)
    if services is None:
        return
    portfolio = services.portfolio_service.get_aggregate_portfolio()
    bot.send_message(
        chat_id,
        build_aggregate_portfolio_message(portfolio, services.user.display_name),
        reply_markup=build_aggregate_portfolio_keyboard(portfolio),
        parse_mode="Markdown",
    )


@bot.message_handler(func=lambda message: message.text in {"Portfolio", "Получить портфолио"})
def get_portfolio_handler(message):
    send_aggregate_portfolio(message.chat.id)


@bot.callback_query_handler(func=lambda call: call.data == PORTFOLIO_ROOT_CALLBACK)
def portfolio_root_callback(call):
    _answer_callback(call)
    send_aggregate_portfolio(call.message.chat.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith(PORTFOLIO_ACCOUNT_PREFIX))
def portfolio_account_callback(call):
    _answer_callback(call)
    chat_id = call.message.chat.id
    services = get_telegram_services_or_notify(chat_id)
    if services is None:
        return
    account_id_text = call.data[len(PORTFOLIO_ACCOUNT_PREFIX):]
    try:
        account_id = int(account_id_text)
        account_context = services.account_registry.get_account_context(account_id)
    except (TypeError, ValueError, UnknownInvestmentAccountError):
        bot.send_message(
            chat_id,
            "⚠️ This investment account is unavailable. Refresh the aggregate portfolio.",
            reply_markup=build_account_portfolio_keyboard(),
        )
        return

    portfolio = services.portfolio_service.get_account_portfolio(account_context)
    bot.send_message(
        chat_id,
        build_account_portfolio_message(portfolio),
        reply_markup=build_account_portfolio_keyboard(),
        parse_mode="Markdown",
    )


def _answer_callback(call) -> None:
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass


def _format_account_type(account_type: str) -> str:
    labels = {
        "brokerage": "Brokerage",
        "iis": "IIS",
    }
    normalized = str(account_type).strip().lower()
    return labels.get(normalized, normalized.replace("_", " ").title())
