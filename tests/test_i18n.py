from channel_manager_bot.i18n import (
    LANGUAGES,
    TRANSLATIONS,
    normalize_language,
    set_current_language,
    tr,
)
from channel_manager_bot.keyboards import main_menu


def test_all_languages_have_the_complete_primary_interface_catalog():
    expected_keys = set(TRANSLATIONS["es"])

    assert len(LANGUAGES) == 12
    assert all(expected_keys <= set(TRANSLATIONS[item.code]) for item in LANGUAGES)


def test_language_context_translates_start_and_primary_menu():
    token = set_current_language("en")
    try:
        labels = [button.text for row in main_menu().inline_keyboard for button in row]

        assert tr("home_title") == "Administration panel"
        assert "Welcome to Workspace" in tr("start", workspace="Workspace")
        assert "📝 Create post" in labels
        assert "🇺🇸 Language: English" in labels
    finally:
        set_current_language("es")
        del token


def test_unknown_language_falls_back_to_spanish():
    assert normalize_language("unknown") == "es"
    assert tr("members", locale="unknown") == "Miembros"
