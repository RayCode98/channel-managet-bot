from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def next_recurrence_at(
    scheduled_at: datetime,
    interval_days: int,
    now: datetime,
    timezone_name: str = "UTC",
) -> datetime:
    if not 1 <= interval_days <= 365:
        raise ValueError("interval_days must be between 1 and 365")
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        timezone = ZoneInfo("UTC")
    next_local = scheduled_at.astimezone(timezone) + timedelta(days=interval_days)
    next_at = next_local.astimezone(UTC)
    while next_at <= now:
        next_local += timedelta(days=interval_days)
        next_at = next_local.astimezone(UTC)
    return next_at
