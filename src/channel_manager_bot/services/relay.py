from collections import deque

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

COPYABLE_CONTENT_TYPES = frozenset(
    {
        "animation",
        "audio",
        "contact",
        "dice",
        "document",
        "game",
        "location",
        "photo",
        "poll",
        "sticker",
        "story",
        "text",
        "venue",
        "video",
        "video_note",
        "voice",
    }
)


def is_copyable_content_type(content_type) -> bool:
    value = getattr(content_type, "value", content_type)
    return value in COPYABLE_CONTENT_TYPES


def would_create_cycle(edges: set[tuple[int, int]], source: int, destination: int) -> bool:
    if source == destination:
        return True
    adjacency: dict[int, set[int]] = {}
    for edge_source, edge_destination in edges:
        adjacency.setdefault(edge_source, set()).add(edge_destination)

    pending = [destination]
    visited: set[int] = set()
    while pending:
        current = pending.pop()
        if current == source:
            return True
        if current in visited:
            continue
        visited.add(current)
        pending.extend(adjacency.get(current, set()) - visited)
    return False


def url_only_markup(markup: InlineKeyboardMarkup | None) -> InlineKeyboardMarkup | None:
    if markup is None:
        return None
    rows = []
    for row in markup.inline_keyboard:
        url_buttons = [
            InlineKeyboardButton(
                text=button.text,
                url=button.url,
                style=getattr(button, "style", None),
            )
            for button in row
            if button.url
        ]
        if url_buttons:
            rows.append(url_buttons)
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


_RECENT_LIMIT = 5000
_recent_order: deque[tuple[int, int]] = deque()
_recent_set: set[tuple[int, int]] = set()


def remember_relayed_message(chat_id: int, message_id: int) -> None:
    key = (chat_id, message_id)
    if key in _recent_set:
        return
    if len(_recent_order) >= _RECENT_LIMIT:
        _recent_set.discard(_recent_order.popleft())
    _recent_order.append(key)
    _recent_set.add(key)


def was_recently_relayed(chat_id: int, message_id: int) -> bool:
    return (chat_id, message_id) in _recent_set
