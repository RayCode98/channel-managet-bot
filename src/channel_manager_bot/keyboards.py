import uuid
from collections import defaultdict

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .models import (
    Channel,
    FarewellButton,
    JoinRequirement,
    PublicationButton,
    RequirementChat,
    TemplateButton,
    WelcomeButton,
)
from .services.join_filters import SCRIPT_OPTIONS


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


def recurrence_label(days: int | None) -> str:
    if not days:
        return "Una sola vez"
    if days == 1:
        return "Cada día"
    return f"Cada {days} días"


def main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Crear publicación", callback_data="pub:new")
    builder.button(text="🗓 Plan de contenido", callback_data="plan:page:0")
    builder.button(text="🧩 Plantillas", callback_data="tpl:list")
    builder.button(text="👋 Bienvenidas", callback_data="feature:channels:welcome")
    builder.button(text="🚪 Despedidas", callback_data="feature:channels:farewell")
    builder.button(text="🪄 Autocompletado", callback_data="feature:channels:auto")
    builder.button(text="✍️ Firmas", callback_data="feature:channels:signature")
    builder.button(text="🛡 Filtros de unión", callback_data="feature:channels:joinfilter")
    builder.button(text="📚 Historial", callback_data="pub:list")
    builder.button(text="📢 Mis canales", callback_data="channels:list")
    builder.button(text="📊 Estadísticas", callback_data="stats:show")
    builder.button(text="⚙️ Automatizaciones", callback_data="settings:show")
    builder.adjust(1, 2, 2, 2, 2, 2, 1)
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
            [InlineKeyboardButton(text="🔄 Sincronizar ahora", callback_data="channels:refresh")],
            [InlineKeyboardButton(text="⬅️ Menú principal", callback_data="home")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def channel_detail_menu(channel: Channel) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Actualizar información",
                    callback_data=f"channel:refresh:{channel.telegram_chat_id}",
                )
            ],
            [InlineKeyboardButton(text="⬅️ Mis canales", callback_data="channels:list")],
        ]
    )


def feature_channels_menu(channels: list[Channel], kind: str) -> InlineKeyboardMarkup:
    def destination(channel: Channel) -> str:
        if kind == "welcome":
            return f"welcome:menu:{channel.telegram_chat_id}"
        if kind == "farewell":
            return f"farewell:menu:{channel.telegram_chat_id}"
        if kind == "joinfilter":
            return f"jfilter:menu:{channel.telegram_chat_id}"
        return f"posttext:menu:{kind}:{channel.telegram_chat_id}"

    def enabled(channel: Channel) -> bool:
        return {
            "welcome": channel.welcome_enabled,
            "farewell": channel.farewell_enabled,
            "auto": channel.autocomplete_enabled,
            "signature": channel.signature_enabled,
            "joinfilter": bool(
                channel.join_name_filter_enabled
                or (channel.join_requirement and channel.join_requirement.enabled)
            ),
        }[kind]

    rows = [
        [
            InlineKeyboardButton(
                text=f"{'✅' if enabled(channel) else '❌'} {channel.title}"[:64],
                callback_data=destination(channel),
            )
        ]
        for channel in channels
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Menú principal", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def join_filter_menu(channel: Channel) -> InlineKeyboardMarkup:
    requirement_enabled = bool(channel.join_requirement and channel.join_requirement.enabled)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=(
                        "🔤 Filtro de escritura: "
                        f"{'✅' if channel.join_name_filter_enabled else '❌'}"
                    ),
                    callback_data=f"jfilter:alpha:{channel.telegram_chat_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"🔗 Forzar unión: {'✅' if requirement_enabled else '❌'}",
                    callback_data=f"jfilter:force:{channel.telegram_chat_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Canales con filtros",
                    callback_data="feature:channels:joinfilter",
                )
            ],
        ]
    )


def alphabet_filter_menu(
    channel_id: int, selected_scripts: set[str], enabled: bool
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    current_row: list[InlineKeyboardButton] = []
    for code, label in SCRIPT_OPTIONS:
        current_row.append(
            InlineKeyboardButton(
                text=f"{'✅' if code in selected_scripts else '▫️'} {label}"[:64],
                callback_data=f"jfilter:script:{code}:{channel_id}",
            )
        )
        if len(current_row) == 2:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)
    rows.extend(
        [
            [
                InlineKeyboardButton(
                    text=f"Filtro: {'✅ Activo' if enabled else '❌ Desactivado'}",
                    callback_data=f"jfilter:atoggle:{channel_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Filtros del canal", callback_data=f"jfilter:menu:{channel_id}"
                )
            ],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def force_join_menu(channel_id: int, requirement: JoinRequirement | None) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="🎯 Elegir canal o grupo requerido",
                callback_data=f"jfilter:targets:{channel_id}",
            )
        ]
    ]
    if requirement is not None:
        rows.extend(
            [
                [
                    InlineKeyboardButton(
                        text=f"Forzar unión: {'✅ Activo' if requirement.enabled else '❌ Desactivado'}",
                        callback_data=f"jfilter:ftoggle:{channel_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🗑 Quitar requisito",
                        callback_data=f"jfilter:fclear:{channel_id}",
                    )
                ],
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ Filtros del canal", callback_data=f"jfilter:menu:{channel_id}"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def force_target_menu(
    source_channel_id: int,
    channels: list[Channel],
    groups: list[RequirementChat],
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"📢 {channel.title}"[:64],
                callback_data=(f"jfilter:target:c:{channel.telegram_chat_id}:{source_channel_id}"),
            )
        ]
        for channel in channels
        if channel.telegram_chat_id != source_channel_id
    ]
    rows.extend(
        [
            [
                InlineKeyboardButton(
                    text=f"👥 {group.title}"[:64],
                    callback_data=(
                        f"jfilter:target:g:{group.telegram_chat_id}:{source_channel_id}"
                    ),
                )
            ]
            for group in groups
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ Forzar unión", callback_data=f"jfilter:force:{source_channel_id}"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def join_verification_menu(
    invite_url: str, source_channel_id: int, user_id: int
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Unirme al canal o grupo", url=invite_url)],
            [
                InlineKeyboardButton(
                    text="✅ Ya me uní, verificar",
                    callback_data=f"joinverify:{source_channel_id}:{user_id}",
                )
            ],
        ]
    )


def welcome_menu(channel: Channel) -> InlineKeyboardMarkup:
    configured = bool(channel.welcome_source_message_id)
    rows = [
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
    ]
    if channel.welcome_buttons:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🧹 Administrar botones",
                    callback_data=f"welcome:manage:{channel.telegram_chat_id}",
                )
            ]
        )
    if configured:
        rows.append(
            [
                InlineKeyboardButton(
                    text="👁 Vista previa",
                    callback_data=f"welcome:preview:{channel.telegram_chat_id}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text=f"Bienvenida: {'✅' if channel.welcome_enabled else '❌'}",
                callback_data=f"welcome:toggle:{channel.telegram_chat_id}",
            )
        ]
    )
    if configured:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🗑 Borrar bienvenida",
                    callback_data=f"welcome:clear:{channel.telegram_chat_id}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ Canales con bienvenida",
                callback_data="feature:channels:welcome",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def channel_post_text_menu(channel: Channel, kind: str) -> InlineKeyboardMarkup:
    if kind == "auto":
        configured = bool(channel.autocomplete_text)
        enabled = channel.autocomplete_enabled
        configure_label = "🪄 Configurar autocompletado"
    else:
        configured = bool(channel.signature_text)
        enabled = channel.signature_enabled
        configure_label = "✍️ Configurar firma"

    rows = [
        [
            InlineKeyboardButton(
                text=configure_label,
                callback_data=f"posttext:set:{kind}:{channel.telegram_chat_id}",
            )
        ]
    ]
    if configured:
        rows.extend(
            [
                [
                    InlineKeyboardButton(
                        text="👁 Vista previa",
                        callback_data=f"posttext:preview:{kind}:{channel.telegram_chat_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"Estado: {'✅ Activo' if enabled else '❌ Desactivado'}",
                        callback_data=f"posttext:toggle:{kind}:{channel.telegram_chat_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🗑 Borrar texto",
                        callback_data=f"posttext:clear:{kind}:{channel.telegram_chat_id}",
                    )
                ],
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ Volver a canales",
                callback_data=f"feature:channels:{kind}",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def welcome_buttons_menu(channel_id: int, buttons: list[WelcomeButton]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"🗑 {button.text}"[:64], callback_data=f"welcome:bdel:{button.id}"
            )
        ]
        for button in sorted(buttons, key=lambda item: (item.row_index, item.position))
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ Volver a bienvenida", callback_data=f"welcome:menu:{channel_id}"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def farewell_menu(channel: Channel) -> InlineKeyboardMarkup:
    configured = bool(channel.farewell_source_message_id)
    rows = [
        [
            InlineKeyboardButton(
                text="🖼 Configurar despedida",
                callback_data=f"farewell:content:{channel.telegram_chat_id}",
            )
        ],
        [
            InlineKeyboardButton(
                text="🔗 Configurar botones",
                callback_data=f"farewell:buttons:{channel.telegram_chat_id}",
            )
        ],
    ]
    if channel.farewell_buttons:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🧹 Administrar botones",
                    callback_data=f"farewell:manage:{channel.telegram_chat_id}",
                )
            ]
        )
    if configured:
        rows.append(
            [
                InlineKeyboardButton(
                    text="👁 Vista previa",
                    callback_data=f"farewell:preview:{channel.telegram_chat_id}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text=f"Despedida: {'✅' if channel.farewell_enabled else '❌'}",
                callback_data=f"farewell:toggle:{channel.telegram_chat_id}",
            )
        ]
    )
    if configured:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🗑 Borrar despedida",
                    callback_data=f"farewell:clear:{channel.telegram_chat_id}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ Canales con despedida",
                callback_data="feature:channels:farewell",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def farewell_buttons_menu(channel_id: int, buttons: list[FarewellButton]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"🗑 {button.text}"[:64], callback_data=f"farewell:bdel:{button.id}"
            )
        ]
        for button in sorted(buttons, key=lambda item: (item.row_index, item.position))
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ Volver a despedida", callback_data=f"farewell:menu:{channel_id}"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def composer_menu(
    publication_id: uuid.UUID, button_count: int, delete_after_minutes: int | None = None
) -> InlineKeyboardMarkup:
    short_id = str(publication_id)
    rows = []
    if button_count < 20:
        rows.append(
            [InlineKeyboardButton(text="➕ Agregar botón", callback_data=f"pub:button:{short_id}")]
        )
    if button_count:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🧹 Administrar botones", callback_data=f"pub:buttons:{short_id}"
                )
            ]
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
                    text="🔁 Programar recurrente", callback_data=f"pub:repeat:{publication_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Cancelar", callback_data=f"pub:cancel:{publication_id}"
                )
            ],
        ]
    )


def recurrence_interval_menu(publication_id: uuid.UUID) -> InlineKeyboardMarkup:
    choices = [
        ("Cada día", 1),
        ("Cada 2 días", 2),
        ("Cada 3 días", 3),
        ("Cada semana", 7),
        ("Cada 2 semanas", 14),
        ("Cada 30 días", 30),
    ]
    rows = [
        [
            InlineKeyboardButton(
                text=label,
                callback_data=f"pub:setrepeat:{publication_id}:{days}",
            )
        ]
        for label, days in choices
    ]
    rows.extend(
        [
            [
                InlineKeyboardButton(
                    text="✏️ Otro intervalo", callback_data=f"pub:repeatcustom:{publication_id}"
                )
            ],
            [InlineKeyboardButton(text="⬅️ Volver", callback_data=f"pub:time:{publication_id}")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def recurrence_start_menu(publication_id: uuid.UUID, days: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Comenzar ahora",
                    callback_data=f"pub:repeatnow:{publication_id}:{days}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗓 Elegir primera fecha",
                    callback_data=f"pub:repeatdate:{publication_id}:{days}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Cambiar intervalo", callback_data=f"pub:repeat:{publication_id}"
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
        [InlineKeyboardButton(text="🚀 Usar plantilla", callback_data=f"tpl:use:{template_id}")],
        [InlineKeyboardButton(text="👁 Vista previa", callback_data=f"tpl:preview:{template_id}")],
    ]
    if button_count < 20:
        rows.append(
            [
                InlineKeyboardButton(
                    text="➕ Agregar botón", callback_data=f"tpl:button:{template_id}"
                )
            ]
        )
    if button_count:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🧹 Administrar botones", callback_data=f"tpl:buttons:{template_id}"
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


def template_buttons_menu(
    template_id: uuid.UUID, buttons: list[TemplateButton]
) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"🗑 {button.text}"[:64], callback_data=f"tpl:bdel:{button.id}")]
        for button in sorted(buttons, key=lambda item: (item.row_index, item.position))
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ Volver a la plantilla", callback_data=f"tpl:open:{template_id}"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def publication_buttons_menu(
    publication_id: uuid.UUID, buttons: list[PublicationButton]
) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"🗑 {button.text}"[:64], callback_data=f"pub:bdel:{button.id}")]
        for button in sorted(buttons, key=lambda item: (item.row_index, item.position))
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ Volver a la publicación", callback_data=f"pub:edit:{publication_id}"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
