def telegram_text_length(value: str) -> int:
    """Length used by Telegram entity offsets (UTF-16 code units)."""
    return len(value.encode("utf-16-le")) // 2
