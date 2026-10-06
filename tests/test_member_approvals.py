from datetime import UTC, datetime

import pytest

from channel_manager_bot.services.member_approvals import (
    REAL_PENDING_REQUEST_OUTCOMES,
    next_scheduled_run,
)


def test_next_scheduled_run_advances_past_missed_intervals():
    scheduled = datetime(2026, 9, 4, 6, tzinfo=UTC)
    now = datetime(2026, 9, 4, 20, tzinfo=UTC)

    assert next_scheduled_run(scheduled, now, 6) == datetime(2026, 9, 5, 0, tzinfo=UTC)


def test_next_scheduled_run_rejects_unlisted_interval():
    now = datetime(2026, 9, 4, 20, tzinfo=UTC)

    with pytest.raises(ValueError):
        next_scheduled_run(now, now, 5)


def test_real_pending_outcomes_include_verification_but_exclude_resolved_events():
    assert "requirement_pending" in REAL_PENDING_REQUEST_OUTCOMES
    assert "approval_retry" in REAL_PENDING_REQUEST_OUTCOMES
    assert "declined_manual" not in REAL_PENDING_REQUEST_OUTCOMES
    assert "request_unavailable" not in REAL_PENDING_REQUEST_OUTCOMES
