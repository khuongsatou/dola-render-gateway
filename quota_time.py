"""Quota-day calculations shared by API-key and account limits."""
from datetime import date, datetime, time as dt_time, timedelta, timezone
from zoneinfo import ZoneInfo

import config


def _timezone(tz_name: str | None = None):
    name = tz_name or config.LIMIT_RESET_TZ
    try:
        return ZoneInfo(name)
    except Exception:
        offsets = {"Asia/Tokyo": 9, "Asia/Hong_Kong": 8, "UTC": 0}
        return timezone(timedelta(hours=offsets.get(name, 9)))


def _to_timestamp(now: float | datetime | None = None) -> float:
    if now is None:
        return datetime.now(timezone.utc).timestamp()
    if isinstance(now, datetime):
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return now.timestamp()
    return float(now)


def day_key(
    now: float | datetime | None = None,
    tz_name: str | None = None,
) -> str:
    """Returns YYYY-MM-DD for the configured quota timezone."""
    tz = _timezone(tz_name)
    return datetime.fromtimestamp(_to_timestamp(now), tz).date().isoformat()


def day_bounds(
    day: str | None = None,
    tz_name: str | None = None,
) -> tuple[float, float]:
    """Returns inclusive start and exclusive end epoch timestamps for a quota day."""
    tz = _timezone(tz_name)
    day_value = date.fromisoformat(day) if day else date.fromisoformat(day_key(tz_name=tz_name))
    start = datetime.combine(day_value, dt_time.min, tzinfo=tz).timestamp()
    end = datetime.combine(day_value + timedelta(days=1), dt_time.min, tzinfo=tz).timestamp()
    return start, end


def next_reset_ts(
    now: float | datetime | None = None,
    tz_name: str | None = None,
) -> float:
    """Returns the next midnight boundary in the configured quota timezone."""
    return day_bounds(day_key(now, tz_name), tz_name)[1]
