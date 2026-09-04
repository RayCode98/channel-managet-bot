from datetime import UTC, datetime

import pytest

from channel_manager_bot.services.recurrence import next_recurrence_at


def test_next_recurrence_skips_missed_occurrences_without_bursting():
    scheduled_at = datetime(2026, 1, 1, 18, 0, tzinfo=UTC)
    now = datetime(2026, 1, 10, 19, 0, tzinfo=UTC)

    result = next_recurrence_at(scheduled_at, interval_days=2, now=now)

    assert result == datetime(2026, 1, 11, 18, 0, tzinfo=UTC)


def test_daily_recurrence_preserves_local_hour_across_dst():
    # 09:00 en Nueva York antes del cambio de horario de verano.
    scheduled_at = datetime(2026, 3, 7, 14, 0, tzinfo=UTC)
    now = datetime(2026, 3, 7, 15, 0, tzinfo=UTC)

    result = next_recurrence_at(
        scheduled_at,
        interval_days=1,
        now=now,
        timezone_name="America/New_York",
    )

    # Al día siguiente 09:00 local corresponde a 13:00 UTC.
    assert result == datetime(2026, 3, 8, 13, 0, tzinfo=UTC)


def test_recurrence_rejects_out_of_range_intervals():
    scheduled_at = datetime(2026, 1, 1, 18, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="between 1 and 365"):
        next_recurrence_at(scheduled_at, interval_days=0, now=scheduled_at)
