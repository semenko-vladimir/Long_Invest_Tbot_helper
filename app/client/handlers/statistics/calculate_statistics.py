from app.client.handlers.utils.message_utils import send_or_edit_message
from app.services.statistics import StatisticsService, StatisticsView


def format_statistics_view(view: StatisticsView) -> str:
    if view.error:
        return f"*Statistics error*\n\n`{view.error}`"

    if view.empty:
        return "*Statistics*\n\nNo stored data yet."

    top_tickers = ", ".join(f"{item.ticker}: {item.count}" for item in view.top_tickers) or "none"
    note = ""
    if view.orders_no_timestamp_note:
        note = "\nManual orders do not store timestamps yet, so order totals are shown all time."

    return (
        "*Statistics*\n\n"
        f"Period: `{view.period_label.lower()}`\n"
        f"Buy records: `{view.buy_record_count}`\n"
        f"Buy amount: `{view.buy_record_value_display}`\n"
        f"Margin records: `{view.margin_record_count}`\n"
        f"Margin total: `{view.margin_record_total:.2f}%`\n"
        f"Manual orders: `{view.order_count}`\n"
        f"Manual buys: `{view.order_buy_count}`\n"
        f"Manual sells: `{view.order_sell_count}`\n"
        f"Manual order value: `{view.order_value_display}`\n"
        f"Top tickers: `{top_tickers}`"
        f"{note}"
    )


def calculate_statistics(days, chat_id, statistics_service: StatisticsService = None):
    try:
        period_days = None
        if days != "full":
            period_days = int(days)

        service = statistics_service or StatisticsService()
        view = service.get_statistics_view(period_days=period_days)
        send_or_edit_message(chat_id, format_statistics_view(view))
    except Exception as e:
        send_or_edit_message(chat_id, f"*Statistics error*\n\n`{str(e)}`")
