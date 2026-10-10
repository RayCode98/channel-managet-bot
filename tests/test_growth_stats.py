from datetime import UTC, datetime

from channel_manager_bot.handlers.campaigns import valid_campaign_url
from channel_manager_bot.services.growth_stats import period_start


def test_period_start_clamps_to_a_safe_reporting_window():
    now = datetime(2026, 10, 7, 12, tzinfo=UTC)

    assert period_start(0, now) == datetime(2026, 10, 6, 12, tzinfo=UTC)
    assert period_start(30, now) == datetime(2026, 9, 7, 12, tzinfo=UTC)
    assert period_start(999, now) == datetime(2025, 10, 7, 12, tzinfo=UTC)


def test_campaign_urls_only_allow_telegram_or_web_destinations():
    assert valid_campaign_url("https://example.com/landing")
    assert valid_campaign_url("tg://resolve?domain=canal")
    assert not valid_campaign_url("https://")
    assert not valid_campaign_url("javascript:alert(1)")
    assert not valid_campaign_url("canal.example.com")
