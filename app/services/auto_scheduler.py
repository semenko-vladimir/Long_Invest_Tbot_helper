from datetime import date, timedelta
import logging

logger = logging.getLogger(__name__)

# Known MOEX non-trading days — (month, day), applies to any year
MOEX_HOLIDAY_MMDD: set[tuple[int, int]] = {
    (1, 1), (1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8),  # New Year
    (2, 23),   # Defender of the Fatherland Day
    (3, 8),    # International Women's Day
    (5, 1),    # Labour Day
    (5, 9),    # Victory Day
    (6, 12),   # Russia Day
    (11, 4),   # National Unity Day
    (12, 31),  # New Year's Eve (shortened/closed)
}


def is_trading_day(dt: date) -> bool:
    """Returns True if the given date is a MOEX trading day."""
    if dt.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    if (dt.month, dt.day) in MOEX_HOLIDAY_MMDD:
        return False
    return True


def next_trading_day(dt: date) -> date:
    """Returns the nearest trading day on or after dt."""
    candidate = dt
    while not is_trading_day(candidate):
        candidate += timedelta(days=1)
    return candidate
