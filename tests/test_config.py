from channel_manager_bot.config import Settings


def test_admin_ids_are_parsed_from_csv():
    settings = Settings(
        bot_token="token",
        database_url="postgresql+asyncpg://localhost/test",
        platform_admin_ids="12, 34",
    )
    assert settings.platform_admin_ids == frozenset({12, 34})
