import uuid
from collections import defaultdict

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .models import Channel, PublicationButton


def main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Crear publicación", callback_data="pub:new")
    builder.button(text="📚 Publicaciones", callback_data="pub:list")
    builder.button(text="📢 Mis canales", callback_data="channels:list")
    builder.button(text="📊 Estadísticas", callback_data="stats:show")
    builder.button(text="⚙️ Automatizaciones", callback_data="settings:show")
    builder.adjust(1, 2, 1, 1)
    return builder.as_markup()


def back_home() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Menú principal", callback_data="home")]]
    )


def channels_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Agregar canal", callback_data="channels:add")],
            [InlineKeyboardButton(text="🔄 Actualizar lista", callback_data="channels:list")],
            [InlineKeyboardButton(text="⬅️ Menú principal", callback_data="home")],
        ]
    )


def composer_menu(publication_id: uuid.UUID, button_count: int) -> InlineKeyboardMarkup:
    short_id = str(publication_id)
    rows = []
    if button_count < 20:
        rows.append(
            [InlineKeyboardButton(text="➕ Agregar botón", callback_data=f"pub:button:{short_id}")]
        )
    rows.extend(
        [
            [
                InlineKeyboardButton(
                    text="📢 Elegir canales", callback_data=f"pub:channels:{short_id}"
                )
            ],
            [InlineKeyboardButton(text="❌ Cancelar", callback_data=f"pub:cancel:{short_id}")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def channel_selector(
    publication_id: uuid.UUID, channels: list[Channel], selected: set[int]
) -> InlineKeyboardMarkup:
    rows = []
    for channel in channels:
        mark = "✅" if channel.telegram_chat_id in selected else "☑️"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{mark} {channel.title}"[:64],
                    callback_data=f"pub:toggle:{publication_id}:{channel.telegram_chat_id}",
                )
            ]
        )
    rows.extend(
        [
            [
                InlineKeyboardButton(
                    text="Seleccionar todos", callback_data=f"pub:all:{publication_id}"
                )
            ],
            [InlineKeyboardButton(text="Continuar", callback_data=f"pub:time:{publication_id}")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def timing_menu(publication_id: uuid.UUID) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Publicar ahora", callback_data=f"pub:now:{publication_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗓 Programar fecha", callback_data=f"pub:schedule:{publication_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Cancelar", callback_data=f"pub:cancel:{publication_id}"
                )
            ],
        ]
    )


def settings_menu(auto_approve: bool, welcome_enabled: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Solicitudes automáticas: {'✅' if auto_approve else '❌'}",
                    callback_data="settings:auto_approve",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Bienvenida: {'✅' if welcome_enabled else '❌'}",
                    callback_data="settings:welcome_toggle",
                )
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Editar bienvenida", callback_data="settings:welcome_text"
                )
            ],
            [InlineKeyboardButton(text="⬅️ Menú principal", callback_data="home")],
        ]
    )


def publication_markup(buttons: list[PublicationButton]) -> InlineKeyboardMarkup | None:
    if not buttons:
        return None
    grouped = defaultdict(list)
    for button in sorted(buttons, key=lambda item: (item.row_index, item.position)):
        grouped[button.row_index].append(InlineKeyboardButton(text=button.text, url=button.url))
    return InlineKeyboardMarkup(inline_keyboard=list(grouped.values()))
