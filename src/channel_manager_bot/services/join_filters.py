import unicodedata

from aiogram.enums import ChatMemberStatus

SCRIPT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("latin", "Latino"),
    ("cyrl", "Cirílico"),
    ("greek", "Griego"),
    ("arab", "Árabe / persa / urdu"),
    ("hebr", "Hebreo"),
    ("deva", "Devanagari (hindi)"),
    ("beng", "Bengalí"),
    ("guru", "Gurmukhi (punyabí)"),
    ("gujr", "Gujarati"),
    ("taml", "Tamil"),
    ("telu", "Telugu"),
    ("knda", "Canarés"),
    ("mlym", "Malayalam"),
    ("sinh", "Cingalés"),
    ("thai", "Tailandés"),
    ("laoo", "Lao"),
    ("mymr", "Birmano"),
    ("khmr", "Jemer"),
    ("geor", "Georgiano"),
    ("armn", "Armenio"),
    ("hani", "Han (chino/kanji)"),
    ("kana", "Kana japonés"),
    ("hang", "Hangul coreano"),
    ("ethi", "Etíope"),
)

SCRIPT_LABELS = dict(SCRIPT_OPTIONS)

_NAME_MARKERS: tuple[tuple[str, str], ...] = (
    ("LATIN", "latin"),
    ("CYRILLIC", "cyrl"),
    ("GREEK", "greek"),
    ("ARABIC", "arab"),
    ("HEBREW", "hebr"),
    ("DEVANAGARI", "deva"),
    ("BENGALI", "beng"),
    ("GURMUKHI", "guru"),
    ("GUJARATI", "gujr"),
    ("TAMIL", "taml"),
    ("TELUGU", "telu"),
    ("KANNADA", "knda"),
    ("MALAYALAM", "mlym"),
    ("SINHALA", "sinh"),
    ("THAI", "thai"),
    ("LAO", "laoo"),
    ("MYANMAR", "mymr"),
    ("KHMER", "khmr"),
    ("GEORGIAN", "geor"),
    ("ARMENIAN", "armn"),
    ("HIRAGANA", "kana"),
    ("KATAKANA", "kana"),
    ("HANGUL", "hang"),
    ("ETHIOPIC", "ethi"),
)


def character_script(character: str) -> str | None:
    """Return our stable script code for a Unicode letter."""
    if not unicodedata.category(character).startswith("L"):
        return None
    unicode_name = unicodedata.name(character, "")
    if unicode_name.startswith(("CJK UNIFIED IDEOGRAPH", "CJK COMPATIBILITY IDEOGRAPH")):
        return "hani"
    for marker, code in _NAME_MARKERS:
        if marker in unicode_name:
            return code
    return None


def detect_name_scripts(full_name: str) -> set[str]:
    return {
        script for character in full_name if (script := character_script(character)) is not None
    }


def blocked_name_scripts(full_name: str, blocked_scripts: set[str]) -> set[str]:
    return detect_name_scripts(full_name) & blocked_scripts


def is_current_member(member) -> bool:
    if member.status in {
        ChatMemberStatus.CREATOR,
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.MEMBER,
    }:
        return True
    return member.status == ChatMemberStatus.RESTRICTED and bool(
        getattr(member, "is_member", False)
    )
