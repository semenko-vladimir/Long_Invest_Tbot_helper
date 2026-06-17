import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from app.charts.schemas import POSITION_VALUE_CHART_DISCLAIMER
from app.charts.services import SUPPORTED_CHART_RANGES
from app.client.bot.bot import bot
from app.client.handlers.user_context import get_telegram_services_or_notify


CHART_RANGE_ORDER = ("day", "week", "month", "six_months", "year", "all")
CHART_SUPPORTED_RANGES_TEXT = ", ".join(CHART_RANGE_ORDER)
CHART_PLAIN_ARGUMENTS = {"plain", "no_analytics"}
CHART_CAPTION = (
    "Read-only educational chart. Hindsight-only analytics. Not a trading signal. "
    "Not investment advice. No broker orders were created."
)
MOEX_CHART_CAPTION = (
    "Read-only MOEX ISS chart. Uses delayed public MOEX ISS data. "
    "Hindsight-only analytics. Not a trading signal. Not investment advice. "
    "No broker orders were created."
)
POSITION_CHART_CAPTION = f"Read-only chart. {POSITION_VALUE_CHART_DISCLAIMER}"
CHART_USAGE_TEXT = (
    "Read-only chart usage:\n"
    "/chart SBER month\n\n"
    "Plain chart without analytics:\n"
    "/chart SBER month plain\n"
    "/chart SBER month no_analytics\n\n"
    f"Supported ranges: {CHART_SUPPORTED_RANGES_TEXT}.\n\n"
    f"{CHART_CAPTION}"
)
MOEX_CHART_USAGE_TEXT = (
    "Read-only MOEX ISS chart usage:\n"
    "/moex_chart SBER month\n\n"
    "Plain chart without analytics:\n"
    "/moex_chart SBER month plain\n"
    "/moex_chart SBER month no_analytics\n\n"
    f"Supported ranges: {CHART_SUPPORTED_RANGES_TEXT}.\n\n"
    f"{MOEX_CHART_CAPTION}"
)
POSITION_CHART_USAGE_TEXT = (
    "Current quantity value chart usage:\n"
    "/position_chart SBER month\n\n"
    f"Supported ranges: {CHART_SUPPORTED_RANGES_TEXT}.\n\n"
    f"{POSITION_CHART_CAPTION}"
)
CHART_COMMAND_RE = re.compile(
    r"^\s*/chart(?:@\w+)?\s+([A-Z0-9-]+)\s+(\S+)(?:\s+(\S+))?\s*$",
    re.IGNORECASE,
)
MOEX_CHART_COMMAND_RE = re.compile(
    r"^\s*/moex_chart(?:@\w+)?\s+([A-Z0-9-]+)\s+(\S+)(?:\s+(\S+))?\s*$",
    re.IGNORECASE,
)
POSITION_CHART_COMMAND_RE = re.compile(
    r"^\s*/position_chart(?:@\w+)?\s+([A-Z0-9-]+)\s+(\S+)\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ChartCommand:
    ticker: str
    range_name: str
    include_analytics: bool = True


@dataclass(frozen=True)
class PositionChartCommand:
    ticker: str
    range_name: str


def parse_chart_command(text: Optional[str]) -> Optional[ChartCommand]:
    return _parse_price_chart_command(text, CHART_COMMAND_RE)


def parse_moex_chart_command(text: Optional[str]) -> Optional[ChartCommand]:
    return _parse_price_chart_command(text, MOEX_CHART_COMMAND_RE)


def _parse_price_chart_command(text: Optional[str], pattern) -> Optional[ChartCommand]:
    if not text:
        return None

    match = pattern.match(text)
    if not match:
        return None

    ticker, range_name, analytics_arg = match.groups()
    normalized_ticker = normalize_chart_ticker(ticker)
    normalized_range = range_name.strip().lower().replace("-", "_")
    if not normalized_ticker or normalized_range not in SUPPORTED_CHART_RANGES:
        return None

    include_analytics = True
    if analytics_arg is not None:
        normalized_analytics = analytics_arg.strip().lower().replace("-", "_")
        if normalized_analytics not in CHART_PLAIN_ARGUMENTS:
            return None
        include_analytics = False

    return ChartCommand(
        ticker=normalized_ticker,
        range_name=normalized_range,
        include_analytics=include_analytics,
    )


def parse_position_chart_command(text: Optional[str]) -> Optional[PositionChartCommand]:
    if not text:
        return None

    match = POSITION_CHART_COMMAND_RE.match(text)
    if not match:
        return None

    ticker, range_name = match.groups()
    normalized_ticker = normalize_chart_ticker(ticker)
    normalized_range = range_name.strip().lower().replace("-", "_")
    if not normalized_ticker or normalized_range not in SUPPORTED_CHART_RANGES:
        return None

    return PositionChartCommand(ticker=normalized_ticker, range_name=normalized_range)


def send_chart_usage(chat_id: int) -> None:
    bot.send_message(chat_id=chat_id, text=CHART_USAGE_TEXT)


def send_moex_chart_usage(chat_id: int) -> None:
    bot.send_message(chat_id=chat_id, text=MOEX_CHART_USAGE_TEXT)


def send_position_chart_usage(chat_id: int) -> None:
    bot.send_message(chat_id=chat_id, text=POSITION_CHART_USAGE_TEXT)


def send_chart(chat_id: int, command: ChartCommand) -> None:
    services = get_telegram_services_or_notify(chat_id)
    if services is None:
        return

    try:
        result = services.chart_image_service.render_png(
            command.ticker,
            command.range_name,
            include_analytics=command.include_analytics,
        )
    except Exception as exc:
        bot.send_message(
            chat_id=chat_id,
            text=(
                "Read-only chart could not be generated.\n\n"
                f"Error: {str(exc)}\n\n"
                f"{CHART_CAPTION}"
            ),
        )
        return

    if result.ok and result.png_bytes is not None:
        bot.send_photo(chat_id=chat_id, photo=result.png_bytes, caption=format_chart_caption(result))
        return

    bot.send_message(chat_id=chat_id, text=format_chart_error(result))


def send_moex_chart(chat_id: int, command: ChartCommand) -> None:
    services = get_telegram_services_or_notify(chat_id)
    if services is None:
        return

    image_service = getattr(services, "moex_chart_image_service", None)
    if image_service is None:
        bot.send_message(
            chat_id=chat_id,
            text=(
                "MOEX ISS chart could not be generated.\n\n"
                "Error: MOEX ISS chart service is not configured.\n\n"
                f"{MOEX_CHART_CAPTION}"
            ),
        )
        return

    try:
        result = image_service.render_png(
            command.ticker,
            command.range_name,
            include_analytics=command.include_analytics,
        )
    except Exception as exc:
        bot.send_message(
            chat_id=chat_id,
            text=(
                "MOEX ISS chart could not be generated.\n\n"
                f"Error: {str(exc)}\n\n"
                f"{MOEX_CHART_CAPTION}"
            ),
        )
        return

    if result.ok and result.png_bytes is not None:
        bot.send_photo(chat_id=chat_id, photo=result.png_bytes, caption=format_moex_chart_caption(result))
        return

    bot.send_message(chat_id=chat_id, text=format_moex_chart_error(result))


def send_position_chart(chat_id: int, command: PositionChartCommand) -> None:
    services = get_telegram_services_or_notify(chat_id)
    if services is None:
        return

    try:
        result = services.chart_image_service.render_png(
            command.ticker,
            command.range_name,
            include_analytics=False,
            mode="position_value",
        )
    except Exception as exc:
        bot.send_message(
            chat_id=chat_id,
            text=(
                "Current quantity value chart could not be generated.\n\n"
                f"Error: {str(exc)}\n\n"
                f"{POSITION_CHART_CAPTION}"
            ),
        )
        return

    if result.ok and result.png_bytes is not None:
        bot.send_photo(chat_id=chat_id, photo=result.png_bytes, caption=format_position_chart_caption(result))
        return

    bot.send_message(chat_id=chat_id, text=format_position_chart_error(result))


def format_chart_error(result) -> str:
    errors = [str(error).strip() for error in getattr(result, "errors", []) if str(error).strip()]
    if errors:
        detail = "; ".join(errors)
    else:
        gaps = [
            str(getattr(gap, "description", "")).strip()
            for gap in getattr(result, "data_gaps", [])
            if str(getattr(gap, "description", "")).strip()
        ]
        detail = "; ".join(gaps) if gaps else "No chart image was returned."

    return f"Read-only chart could not be generated.\n\nError: {detail}\n\n{CHART_CAPTION}"


def format_moex_chart_error(result) -> str:
    errors = [str(error).strip() for error in getattr(result, "errors", []) if str(error).strip()]
    if errors:
        detail = "; ".join(errors)
    else:
        gaps = [
            str(getattr(gap, "description", "")).strip()
            for gap in getattr(result, "data_gaps", [])
            if str(getattr(gap, "description", "")).strip()
        ]
        detail = "; ".join(gaps) if gaps else "No chart image was returned."

    return f"MOEX ISS chart could not be generated.\n\nError: {detail}\n\n{MOEX_CHART_CAPTION}"


def format_position_chart_error(result) -> str:
    errors = [str(error).strip() for error in getattr(result, "errors", []) if str(error).strip()]
    if errors:
        detail = "; ".join(errors)
    else:
        gaps = [
            str(getattr(gap, "description", "")).strip()
            for gap in getattr(result, "data_gaps", [])
            if str(getattr(gap, "description", "")).strip()
        ]
        detail = "; ".join(gaps) if gaps else "No chart image was returned."

    return f"Current quantity value chart could not be generated.\n\nError: {detail}\n\n{POSITION_CHART_CAPTION}"


def format_chart_caption(result) -> str:
    return f"{CHART_CAPTION}{format_source_suffix(result)}"


def format_moex_chart_caption(result) -> str:
    return f"{MOEX_CHART_CAPTION}{format_source_suffix(result)}"


def format_position_chart_caption(result) -> str:
    return f"{POSITION_CHART_CAPTION}{format_source_suffix(result)}"


def format_source_suffix(result) -> str:
    source = str(getattr(result, "source_name", "") or "").strip()
    fetched_at = getattr(result, "fetched_at", None)
    as_of_date = getattr(result, "as_of_date", None)
    freshness = str(getattr(result, "freshness", "") or "").strip()
    delay_status = str(getattr(result, "delay_status", "") or "").strip()
    candle_count = chart_result_candle_count(result)

    if not source:
        history = getattr(result, "history", None)
        source = str(getattr(history, "source", "") or "").strip()
        fetched_at = fetched_at or getattr(history, "fetched_at", None)
        as_of_date = as_of_date or getattr(history, "as_of_date", None)
        freshness = freshness or str(getattr(history, "freshness", "") or "").strip()
        delay_status = delay_status or str(getattr(history, "delay_status", "") or "").strip()

    if not source:
        position_value = getattr(result, "position_value", None)
        source = str(getattr(position_value, "source", "") or "").strip()
        fetched_at = fetched_at or getattr(position_value, "fetched_at", None)
        as_of_date = as_of_date or getattr(position_value, "as_of_date", None)
        freshness = freshness or str(getattr(position_value, "freshness", "") or "").strip()
        delay_status = delay_status or str(getattr(position_value, "delay_status", "") or "").strip()
        candle_count = candle_count or len(getattr(position_value, "value_series", []) or [])

    if not source:
        return ""

    suffix = f"\n\nSource: {source}"
    suffix = f"{suffix} | Freshness: {normalize_caption_freshness(freshness)}"
    suffix = f"{suffix} | Delay: {normalize_caption_delay(delay_status, source)}"
    if as_of_date:
        suffix = f"{suffix} | As of: {as_of_date}"
    formatted_fetched_at = format_metadata_time(fetched_at)
    if formatted_fetched_at:
        suffix = f"{suffix} | Fetched: {formatted_fetched_at}"
    suffix = f"{suffix} | Candles: {candle_count}"
    return suffix


def chart_result_candle_count(result) -> int:
    history = getattr(result, "history", None)
    candles = getattr(history, "candles", None)
    if candles is not None:
        return len(candles)
    position_value = getattr(result, "position_value", None)
    value_series = getattr(position_value, "value_series", None)
    if value_series is not None:
        return len(value_series)
    return 0


def normalize_caption_freshness(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"current", "latest_available", "stale", "partial"}:
        return normalized
    if "stale" in normalized or "local" in normalized:
        return "stale"
    if "partial" in normalized:
        return "partial"
    if "current" in normalized:
        return "current"
    return "latest_available"


def normalize_caption_delay(value: str, source: str = "") -> str:
    normalized = str(value or "").strip().lower()
    source_text = str(source or "").strip().lower()
    if normalized in {"broker_api", "moex_delayed", "cached"}:
        return normalized
    if "moex" in source_text or "iss" in normalized or "delayed" in normalized:
        return "moex_delayed"
    if "cache" in source_text or "cache" in normalized:
        return "cached"
    return "broker_api"


def format_metadata_time(value) -> str:
    if not isinstance(value, datetime):
        return ""
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value.strftime("%Y-%m-%d %H:%M UTC")


def normalize_chart_ticker(ticker: str) -> str:
    normalized = str(ticker or "").strip().upper()
    return normalized if normalized.replace("-", "").isalnum() else ""


@bot.message_handler(commands=["chart"])
def chart_command_handler(message):
    command = parse_chart_command(getattr(message, "text", None))
    if command is None:
        send_chart_usage(message.chat.id)
        return

    send_chart(message.chat.id, command)


@bot.message_handler(commands=["moex_chart"])
def moex_chart_command_handler(message):
    command = parse_moex_chart_command(getattr(message, "text", None))
    if command is None:
        send_moex_chart_usage(message.chat.id)
        return

    send_moex_chart(message.chat.id, command)


@bot.message_handler(commands=["position_chart"])
def position_chart_command_handler(message):
    command = parse_position_chart_command(getattr(message, "text", None))
    if command is None:
        send_position_chart_usage(message.chat.id)
        return

    send_position_chart(message.chat.id, command)
