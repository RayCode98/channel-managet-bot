from dataclasses import dataclass
from html import escape

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from ..models import Channel, WelcomeButton

MAX_WELCOME_BUTTONS = 20

COLOR_STYLES = {
    "azul": "primary",
    "primary": "primary",
    "verde": "success",
    "success": "success",
    "rojo": "danger",
    "danger": "danger",
    "normal": None,
    "default": None,
    "predeterminado": None,
    "gris": None,
}


@dataclass(frozen=True)
class ParsedWelcomeButton:
    text: str
    url: str
    style: str | None


def parse_welcome_buttons(value: str) -> list[ParsedWelcomeButton]:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if not lines:
        raise ValueError("Envía al menos un botón.")
    if len(lines) > MAX_WELCOME_BUTTONS:
        raise ValueError(f"Puedes configurar hasta {MAX_WELCOME_BUTTONS} botones.")

    parsed = []
    for line_number, line in enumerate(lines, start=1):
        try:
            name_and_url, color = line.rsplit(" - ", 1)
            name, url = name_and_url.split(" - ", 1)
        except ValueError as exc:
            raise ValueError(f"La línea {line_number} debe usar: nombre - url - color") from exc

        name, url, color = name.strip(), url.strip(), color.strip().lower()
        if not 1 <= len(name) <= 64:
            raise ValueError(
                f"El nombre de la línea {line_number} debe tener entre 1 y 64 caracteres."
            )
        if not url.startswith(("https://", "http://", "tg://")) or len(url) > 2048:
            raise ValueError(
                f"La URL de la línea {line_number} debe comenzar con https://, http:// o tg://"
            )
        if color not in COLOR_STYLES:
            raise ValueError(
                f"Color no válido en la línea {line_number}. Usa azul, verde, rojo o normal."
            )
        parsed.append(ParsedWelcomeButton(name, url, COLOR_STYLES[color]))
    return parsed


def render_welcome_text(template: str | None, user_name: str, channel_name: str) -> str:
    text = template or ""
    return text.replace("{nombre}", escape(user_name)).replace("{canal}", escape(channel_name))


def welcome_markup(buttons: list[WelcomeButton]) -> InlineKeyboardMarkup | None:
    if not buttons:
        return None
    rows = [
        [
            InlineKeyboardButton(
                text=button.text,
                url=button.url,
                style=button.style,
            )
        ]
        for button in sorted(buttons, key=lambda item: (item.row_index, item.position))
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def content_from_message(message: Message) -> tuple[str, str, str | None]:
    text = message.html_text
    if message.text:
        return "text", text, None
    if message.photo:
        return "photo", text, message.photo[-1].file_id
    for content_type in ("video", "animation", "audio", "document", "voice"):
        media = getattr(message, content_type)
        if media:
            return content_type, text, media.file_id
    raise ValueError("Tipo de contenido de bienvenida no compatible.")


async def send_channel_welcome(
    bot: Bot,
    chat_id: int,
    channel: Channel,
    user_name: str,
) -> None:
    markup = welcome_markup(channel.welcome_buttons)
    if channel.welcome_content_type:
        text = render_welcome_text(
            channel.welcome_text_template,
            user_name=user_name,
            channel_name=channel.title,
        )
        if channel.welcome_content_type == "text":
            await bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)
            return

        method = getattr(bot, f"send_{channel.welcome_content_type}")
        await method(
            chat_id=chat_id,
            **{channel.welcome_content_type: channel.welcome_file_id},
            caption=text or None,
            reply_markup=markup,
        )
        return

    # Compatibilidad con bienvenidas guardadas antes de v0.3.0.
    if channel.welcome_source_chat_id and channel.welcome_source_message_id:
        await bot.copy_message(
            chat_id=chat_id,
            from_chat_id=channel.welcome_source_chat_id,
            message_id=channel.welcome_source_message_id,
            reply_markup=markup,
        )
