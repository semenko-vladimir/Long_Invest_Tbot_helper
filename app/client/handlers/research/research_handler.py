import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Sequence

from app.client.bot.bot import bot
from app.client.config import get_invest_mode
from app.client.handlers.utils.message_utils import last_messages
from app.integrations.tinvest import TInvestBroker
from app.research.local_fundamentals_adapter import LocalFundamentalsAdapter
from app.research.market_context import MOEXMarketContextAdapter
from app.research.moex_iss_adapter import MOEXISSResearchAdapter
from app.research.schemas import DataGap, ResearchReport
from app.research.services import ResearchReportService, TickerResearchService
from app.research.tinvest_adapter import TInvestDataAdapter
from app.services.user_context import UnknownUserError, UserContext, UserContextResolver
from app.services.user_database import session_factory_for_user


RESEARCH_TEXT_COMMAND_RE = re.compile(r"^\s*research(?:\s+(.+))?\s*$", re.IGNORECASE)
RESEARCH_USAGE_TEXT = (
    "Read-only research usage:\n"
    "/research SBER\n"
    "research SBER\n\n"
    "This only builds an educational report. It is not a trading signal and never "
    "creates or prepares broker orders."
)


@dataclass(frozen=True)
class TelegramResearchServices:
    ticker_research: TickerResearchService
    report_builder: ResearchReportService


_user_context_resolver = UserContextResolver()


def get_telegram_research_services(chat_id: Optional[int | str] = None) -> TelegramResearchServices:
    if chat_id is None:
        return TelegramResearchServices(
            ticker_research=TickerResearchService(
                [
                    TInvestDataAdapter(),
                    MOEXISSResearchAdapter(),
                    LocalFundamentalsAdapter(),
                    MOEXMarketContextAdapter(),
                ]
            ),
            report_builder=ResearchReportService(),
        )

    return build_telegram_research_services(_user_context_resolver.resolve_telegram_chat(chat_id))


def build_telegram_research_services(user_context: UserContext) -> TelegramResearchServices:
    session_factory = session_factory_for_user(user_context)
    broker = TInvestBroker(session_factory=session_factory)
    token_provider = lambda: user_context.active_token(get_invest_mode())
    return TelegramResearchServices(
        ticker_research=TickerResearchService(
            [
                TInvestDataAdapter(broker=broker, token_provider=token_provider),
                MOEXISSResearchAdapter(),
                LocalFundamentalsAdapter(),
                MOEXMarketContextAdapter(),
            ]
        ),
        report_builder=ResearchReportService(),
    )


def parse_research_command_argument(text: Optional[str]) -> Optional[str]:
    if not text:
        return None

    stripped = text.strip()
    if not stripped:
        return None

    command, _, rest = stripped.partition(" ")
    command_name = command.split("@", 1)[0].lower()
    if command_name != "/research":
        return None

    return rest.strip()


def parse_research_text_command(text: Optional[str]) -> Optional[str]:
    if not text:
        return None

    match = RESEARCH_TEXT_COMMAND_RE.match(text)
    if not match:
        return None

    return (match.group(1) or "").strip()


def build_research_report(
    ticker: str,
    services: Optional[TelegramResearchServices] = None,
) -> ResearchReport:
    selected_services = services or get_telegram_research_services()
    adapter_results = selected_services.ticker_research.collect(ticker)
    return selected_services.report_builder.build_report(ticker, adapter_results)


def format_research_report(report: ResearchReport) -> str:
    lines = [
        f"Read-only research: {report.ticker or 'unknown ticker'}",
        f"Ticker: {report.ticker or 'unavailable'}",
        f"Sources: {_format_sources(report.sources)}",
        "",
        _format_instrument_identity(report),
        "",
        _format_company_profile(report),
        "",
        _format_sector_industry(report),
        "",
        _format_financials(report),
        "",
        _format_market_snapshot(report),
        "",
        _format_market_context(report),
        "",
        _format_data_gaps(report.data_gaps),
        "",
        _format_errors(report.errors),
        "",
        "Educational note: this is read-only research, not a trading signal. "
        f"{report.disclaimer}",
    ]
    return "\n".join(line for line in lines if line is not None)


def send_research_usage(chat_id: int) -> None:
    _send_research_message(chat_id, RESEARCH_USAGE_TEXT)


def send_research_report(chat_id: int, ticker: str) -> None:
    normalized_ticker = (ticker or "").strip()
    if not normalized_ticker:
        send_research_usage(chat_id)
        return

    try:
        report = build_research_report(normalized_ticker, get_telegram_research_services(chat_id))
        text = format_research_report(report)
    except UnknownUserError:
        text = "This Telegram chat is not authorized for this local investor assistant."
    except Exception as exc:
        text = (
            "Read-only research could not be built.\n\n"
            f"Error: {str(exc)}\n\n"
            "This is not a trading signal and no broker orders were created or prepared."
        )

    _send_research_message(chat_id, text)


def _send_research_message(chat_id: int, text: str) -> None:
    msg = bot.send_message(chat_id=chat_id, text=text)
    last_messages[chat_id] = msg.message_id


def _format_sources(sources: Sequence[str]) -> str:
    clean_sources = [str(source).strip() for source in sources if str(source).strip()]
    return ", ".join(clean_sources) if clean_sources else "none"


def _format_instrument_identity(report: ResearchReport) -> str:
    identity = report.instrument_identity
    if identity is None:
        return "Instrument identity: unavailable."

    values = [
        ("ticker", identity.ticker),
        ("name", identity.name),
        ("figi", identity.figi),
        ("exchange", identity.exchange),
        ("currency", identity.currency),
    ]
    details = "; ".join(f"{label}: {value}" for label, value in values if _has_value(value))
    return f"Instrument identity: {details or 'partial data only'}."


def _format_market_snapshot(report: ResearchReport) -> str:
    snapshot = report.market_snapshot
    if snapshot is None:
        return "Market snapshot: unavailable."

    details = []
    if snapshot.current_price is not None:
        price = f"{snapshot.current_price:g}" if isinstance(snapshot.current_price, float) else str(snapshot.current_price)
        if snapshot.currency:
            price = f"{price} {snapshot.currency}"
        details.append(f"price: {price}")
    if snapshot.captured_at is not None:
        details.append(f"captured_at: {_format_datetime(snapshot.captured_at)}")

    return f"Market snapshot: {'; '.join(details) if details else 'partial data only'}."


def _format_market_context(report: ResearchReport) -> str:
    context = report.market_context or {}
    indexes = context.get("indexes") if isinstance(context, dict) else None
    if not isinstance(indexes, list) or not indexes:
        return "Market context: unavailable."

    parts = []
    for index in indexes:
        if not isinstance(index, dict):
            continue
        ticker = str(index.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        latest_close = index.get("latest_close")
        as_of_date = str(index.get("as_of_date") or "").strip()
        period = str(index.get("period") or context.get("period") or "").strip()
        change = index.get("recent_change_pct")

        if not isinstance(latest_close, (int, float)):
            parts.append(f"{ticker}: unavailable")
            continue

        detail = f"{ticker}: close {latest_close:g}"
        if isinstance(change, (int, float)):
            detail = f"{detail}, {change:+.2f}%"
            if period:
                detail = f"{detail} over {period}"
        if as_of_date:
            detail = f"{detail}, as of {as_of_date}"
        parts.append(detail)

    if not parts:
        return "Market context: unavailable."

    source = str(context.get("source") or "").strip()
    suffix = f" Source: {source}." if source else ""
    return f"Market context: {'; '.join(parts)}.{suffix}"


def _format_company_profile(report: ResearchReport) -> str:
    profile = report.company_profile or {}
    if not profile:
        return "Company profile: unavailable."

    return f"Company profile: {_format_mapping(profile)}."


def _format_sector_industry(report: ResearchReport) -> str:
    sector_industry = report.sector_industry or {}
    if not sector_industry:
        return "Sector/industry: unavailable."

    return f"Sector/industry: {_format_mapping(sector_industry)}."


def _format_financials(report: ResearchReport) -> str:
    financials = report.financials or {}
    if not financials:
        return "Financials: unavailable."

    return f"Financials: {_format_mapping(financials)}."


def _format_mapping(values: dict) -> str:
    details = [
        f"{str(key).replace('_', ' ')}: {value}"
        for key, value in values.items()
        if _has_value(value)
    ]
    return "; ".join(details) if details else "partial data only"


def _format_data_gaps(data_gaps: Sequence[DataGap]) -> str:
    if not data_gaps:
        return "Data gaps: none reported."

    lines = ["Data gaps:"]
    lines.extend(
        f"- {gap.category} ({gap.severity}): {gap.description}"
        for gap in data_gaps
    )
    return "\n".join(lines)


def _format_errors(errors: Sequence[str]) -> str:
    clean_errors = [str(error).strip() for error in errors if str(error).strip()]
    if not clean_errors:
        return "Errors: none reported."

    lines = ["Errors:"]
    lines.extend(f"- {error}" for error in clean_errors)
    return "\n".join(lines)


def _format_datetime(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat()


def _has_value(value: object) -> bool:
    return value is not None and str(value).strip() != ""


@bot.message_handler(commands=["research"])
def research_command_handler(message):
    ticker = parse_research_command_argument(getattr(message, "text", None))
    send_research_report(message.chat.id, ticker or "")


@bot.message_handler(func=lambda message: parse_research_text_command(getattr(message, "text", None)) is not None)
def research_text_command_handler(message):
    ticker = parse_research_text_command(getattr(message, "text", None))
    send_research_report(message.chat.id, ticker or "")
