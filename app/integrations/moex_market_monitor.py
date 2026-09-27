"""Bulk MOEX ISS stock quotes for read-only market monitoring."""

from dataclasses import dataclass
from datetime import date

from app.integrations.moex_iss import MOEXISSClient, iss_table_to_rows


@dataclass(frozen=True)
class StockQuote:
    ticker: str
    name: str
    last: float
    previous_close: float
    trade_date: date

    @property
    def change_pct(self) -> float:
        return (self.last / self.previous_close - 1) * 100


def fetch_stock_quotes(client: MOEXISSClient, today: date) -> dict[str, StockQuote]:
    path = "/engines/stock/markets/shares/boards/TQBR/securities.json"
    result: dict[str, StockQuote] = {}
    # ISS supports paginated board requests. Stop on the first short page.
    for start in range(0, 10000, 100):
        payload = client._get_json(path, {"start": str(start), "iss.only": "securities,marketdata"})
        securities = iss_table_to_rows(payload, "securities", required=False)
        market = iss_table_to_rows(payload, "marketdata", required=False)
        if not securities:
            break
        by_ticker = {str(row.get("secid") or ""): row for row in market}
        for row in securities:
            ticker = str(row.get("secid") or "")
            live = by_ticker.get(ticker, {})
            try:
                previous = float(row.get("prevprice") or 0)
                last = float(live.get("last") or 0)
                volume = float(live.get("valtoday") or live.get("voltoday") or 0)
                raw_date = str(live.get("lasttradedate") or live.get("tradedate") or live.get("systime") or "")[:10]
                trade_date = date.fromisoformat(raw_date)
            except (TypeError, ValueError):
                continue
            if previous > 0 and last > 0 and volume > 0 and trade_date == today:
                result[ticker] = StockQuote(ticker, str(row.get("shortname") or ticker), last, previous, trade_date)
        if len(securities) < 100:
            break
    return result
