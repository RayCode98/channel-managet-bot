import uuid
from collections import defaultdict

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .models import Channel, PublicationButton, TemplateButton


def ttl_label(minutes: int | None) -> str:
    labels = {
        60: "1 hora",
        360: "6 horas",
        720: "12 horas",
        1440: "24 horas",
        2880: "2 días",
        10080: "7 días",
    }
    return labels.get(minutes, "No")


def main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Crear publicación", callback_data="pub:new")
    builder.button(text="🗓 Plan de contenido", callback_data="plan:page:0")
    builder.button(text="🧩 Plantillas", callback_data="tpl:list")
    builder.button(text="📚 Historial", callback_data="pub:list")
    builder.button(text="📢 Mis canales", callback_data="channels:list")
    builder.button(text="📊 Estadísticas", callback_data="stats:show")
    builder.button(text="⚙️ Automatizaciones", callback_data="settings:show")
    builder.adjust(1, 2, 2, 1, 1)
    return builder.as_markup()


def back_home() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Menú principal", callback_data="home")]]
    )


def channels_menu(channels: list[Channel] | None = None) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"⚙️ {channel.title}"[:64],
                callback_data=f"channel:open:{channel.telegram_chat_id}",
            )
        ]
        for channel in (channels or [])
    ]
    rows.extend(
        [
            [InlineKeyboardButton(text="➕ Agregar canal", callback_data="channels:add")],
            [InlineKeyboardButton(text="🔄 Actualizar lista", callback_data="channels:list")],
            [InlineKeyboardButton(text="⬅️ Menú principal", callback_data="home")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def channel_detail_menu(channel: Channel) -> InlineKeyboardMarkup:
    configured = bool(channel.welcome_source_message_id)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🖼 Configurar bienvenida",
                    callback_data=f"welcome:content:{channel.telegram_chat_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔗 Configurar botones",
                    callback_data=f"welcome:buttons:{channel.telegram_chat_id}",
                )
            ],
            *(
                [
                    [
                        InlineKeyboardButton(
                            text="👁 Vista previa",
                            callback_data=f"welcome:preview:{channel.telegram_chat_id}",
                        )
                    ]
                ]
                if configured
                else []
            ),
            [
                InlineKeyboardButton(
                    text=f"Bienvenida: {'✅' if channel.welcome_enabled else '❌'}",
                    callback_data=f"welcome:toggle:{channel.telegram_chat_id}",
                )
            ],
            *(
                [
                    [
                        InlineKeyboardButton(
                            text="🗑 Borrar bienvenida",
                            callback_data=f"welcome:clear:{channel.telegram_chat_id}",
                        )
                    ]
                ]
                if configured
                else []
            ),
            [InlineKeyboardButton(text="⬅️ Mis canales", callback_data="channels:list")],
        ]
    )


def composer_menu(
    publication_id: uuid.UUID, button_count: int, delete_after_minutes: int | None = None
) -> InlineKeyboardMarkup:
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
                    text=f"🗑 Autoeliminación: {ttl_label(delete_after_minutes)}",
                    callback_data=f"pub:ttl:{short_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📢 Elegir canales", callback_data=f"pub:channels:{short_id}"
                )
            ],
            [InlineKeyboardButton(text="❌ Cancelar", callback_data=f"pub:cancel:{short_id}")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ttl_menu(kind: str, item_id: uuid.UUID) -> InlineKeyboardMarkup:
    choices = [("No eliminar", 0), ("1 hora", 60), ("6 horas", 360), ("12 horas", 720)]
    choices.extend([("24 horas", 1440), ("2 días", 2880), ("7 días", 10080)])
    rows = [
        [
            InlineKeyboardButton(
                text=label,
                callback_data=f"{kind}:setttl:{item_id}:{minutes}",
            )
        ]
        for label, minutes in choices
    ]
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


def settings_menu(auto_approve: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Solicitudes automáticas: {'✅' if auto_approve else '❌'}",
                    callback_data="settings:auto_approve",
                )
            ],
            [InlineKeyboardButton(text="⬅️ Menú principal", callback_data="home")],
        ]
    )


def publication_markup(
    buttons: list[PublicationButton] | list[TemplateButton],
) -> InlineKeyboardMarkup | None:
    if not buttons:
        return None
    grouped = defaultdict(list)
    for button in sorted(buttons, key=lambda item: (item.row_index, item.position)):
        grouped[button.row_index].append(InlineKeyboardButton(text=button.text, url=button.url))
    return InlineKeyboardMarkup(inline_keyboard=list(grouped.values()))


def templates_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Crear plantilla", callback_data="tpl:new")],
            [InlineKeyboardButton(text="⬅️ Menú principal", callback_data="home")],
        ]
    )


def template_detail_menu(
    template_id: uuid.UUID, button_count: int, delete_after_minutes: int | None
) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🚀 Usar plantilla", callback_data=f"tpl:use:{template_id}")]
    ]
    if button_count < 20:
        rows.append(
            [
                InlineKeyboardButton(
                    text="➕ Agregar botón", callback_data=f"tpl:button:{template_id}"
                )
            ]
        )
    rows.extend(
        [
            [
                InlineKeyboardButton(
                    text=f"🗑 Autoeliminación: {ttl_label(delete_after_minutes)}",
                    callback_data=f"tpl:ttl:{template_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Eliminar plantilla", callback_data=f"tpl:delete:{template_id}"
                )
            ],
            [InlineKeyboardButton(text="⬅️ Plantillas", callback_data="tpl:list")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
