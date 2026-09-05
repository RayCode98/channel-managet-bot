from datetime import UTC, datetime

import pytest

from channel_manager_bot.services.member_approvals import next_scheduled_run


def test_next_scheduled_run_advances_past_missed_intervals():
    scheduled = datetime(2026, 9, 4, 6, tzinfo=UTC)
    now = datetime(2026, 9, 4, 20, tzinfo=UTC)

    assert next_scheduled_run(scheduled, now, 6) == datetime(2026, 9, 5, 0, tzinfo=UTC)


def test_next_scheduled_run_rejects_unlisted_interval():
    now = datetime(2026, 9, 4, 20, tzinfo=UTC)

    with pytest.raises(ValueError):
        next_scheduled_run(now, now, 5)
