import logging
from contextvars import ContextVar
from dataclasses import dataclass

from aiogram import BaseMiddleware
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LanguageOption:
    code: str
    flag: str
    name: str


LANGUAGES = (
    LanguageOption("es", "🇲🇽", "Español"),
    LanguageOption("en", "🇺🇸", "English"),
    LanguageOption("pt", "🇧🇷", "Português"),
    LanguageOption("fr", "🇫🇷", "Français"),
    LanguageOption("de", "🇩🇪", "Deutsch"),
    LanguageOption("it", "🇮🇹", "Italiano"),
    LanguageOption("ru", "🇷🇺", "Русский"),
    LanguageOption("ar", "🇸🇦", "العربية"),
    LanguageOption("hi", "🇮🇳", "हिन्दी"),
    LanguageOption("zh", "🇨🇳", "中文"),
    LanguageOption("ja", "🇯🇵", "日本語"),
    LanguageOption("ko", "🇰🇷", "한국어"),
)
LANGUAGE_BY_CODE = {item.code: item for item in LANGUAGES}


TRANSLATIONS = {
    "es": {
        "create_post": "Crear publicación",
        "content_plan": "Plan de contenido",
        "templates": "Plantillas",
        "welcomes": "Bienvenidas",
        "farewells": "Despedidas",
        "autocomplete": "Autocompletado",
        "signatures": "Firmas",
        "join_filters": "Filtros de unión",
        "relay": "Reenvío",
        "history": "Historial",
        "chats": "Canales y grupos",
        "stats": "Estadísticas",
        "members": "Miembros",
        "language": "Idioma",
        "back_home": "Menú principal",
        "home_title": "Panel de administración",
        "home_prompt": "¿Qué deseas hacer?",
        "cancelled": "Operación cancelada.",
        "language_title": "Idioma de la interfaz",
        "language_prompt": "Selecciona el idioma para este espacio de trabajo.",
        "language_saved": "Idioma actualizado a {language}.",
        "start": (
            "👋 <b>Bienvenido a {workspace}</b>\n\n"
            "Administra tus canales y grupos desde un solo lugar:\n\n"
            "• crea, programa y repite publicaciones;\n"
            "• reutiliza plantillas y organiza tu plan de contenido;\n"
            "• configura bienvenidas, firmas, filtros y miembros;\n"
            "• reenvía contenido automáticamente entre tus chats;\n"
            "• consulta entregas y estadísticas.\n\n"
            "Todo se configura desde Telegram. Elige una opción para comenzar."
        ),
    },
    "en": {
        "create_post": "Create post",
        "content_plan": "Content plan",
        "templates": "Templates",
        "welcomes": "Welcomes",
        "farewells": "Farewells",
        "autocomplete": "Auto-complete",
        "signatures": "Signatures",
        "join_filters": "Join filters",
        "relay": "Forwarding",
        "history": "History",
        "chats": "Channels and groups",
        "stats": "Statistics",
        "members": "Members",
        "language": "Language",
        "back_home": "Main menu",
        "home_title": "Administration panel",
        "home_prompt": "What would you like to do?",
        "cancelled": "Operation cancelled.",
        "language_title": "Interface language",
        "language_prompt": "Select the language for this workspace.",
        "language_saved": "Language changed to {language}.",
        "start": (
            "👋 <b>Welcome to {workspace}</b>\n\n"
            "Manage your channels and groups from one place:\n\n"
            "• create, schedule and repeat posts;\n"
            "• reuse templates and organize your content plan;\n"
            "• configure welcomes, signatures, filters and members;\n"
            "• forward content automatically between your chats;\n"
            "• review deliveries and statistics.\n\n"
            "Everything is configured from Telegram. Choose an option to begin."
        ),
    },
    "pt": {
        "create_post": "Criar publicação",
        "content_plan": "Plano de conteúdo",
        "templates": "Modelos",
        "welcomes": "Boas-vindas",
        "farewells": "Despedidas",
        "autocomplete": "Autocompletar",
        "signatures": "Assinaturas",
        "join_filters": "Filtros de entrada",
        "relay": "Encaminhamento",
        "history": "Histórico",
        "chats": "Canais e grupos",
        "stats": "Estatísticas",
        "members": "Membros",
        "language": "Idioma",
        "back_home": "Menu principal",
        "home_title": "Painel de administração",
        "home_prompt": "O que deseja fazer?",
        "cancelled": "Operação cancelada.",
        "language_title": "Idioma da interface",
        "language_prompt": "Selecione o idioma deste espaço de trabalho.",
        "language_saved": "Idioma alterado para {language}.",
        "start": (
            "👋 <b>Bem-vindo a {workspace}</b>\n\n"
            "Gerencie seus canais e grupos em um só lugar:\n\n"
            "• crie, programe e repita publicações;\n"
            "• reutilize modelos e organize seu plano de conteúdo;\n"
            "• configure boas-vindas, assinaturas, filtros e membros;\n"
            "• encaminhe conteúdo automaticamente entre seus chats;\n"
            "• consulte entregas e estatísticas.\n\n"
            "Tudo é configurado pelo Telegram. Escolha uma opção para começar."
        ),
    },
    "fr": {
        "create_post": "Créer une publication",
        "content_plan": "Plan de contenu",
        "templates": "Modèles",
        "welcomes": "Messages d’accueil",
        "farewells": "Messages d’adieu",
        "autocomplete": "Texte automatique",
        "signatures": "Signatures",
        "join_filters": "Filtres d’adhésion",
        "relay": "Transfert",
        "history": "Historique",
        "chats": "Canaux et groupes",
        "stats": "Statistiques",
        "members": "Membres",
        "language": "Langue",
        "back_home": "Menu principal",
        "home_title": "Panneau d’administration",
        "home_prompt": "Que souhaitez-vous faire ?",
        "cancelled": "Opération annulée.",
        "language_title": "Langue de l’interface",
        "language_prompt": "Sélectionnez la langue de cet espace de travail.",
        "language_saved": "Langue changée en {language}.",
        "start": (
            "👋 <b>Bienvenue dans {workspace}</b>\n\n"
            "Gérez vos canaux et groupes depuis un seul endroit :\n\n"
            "• créez, programmez et répétez des publications ;\n"
            "• réutilisez des modèles et organisez le plan de contenu ;\n"
            "• configurez accueils, signatures, filtres et membres ;\n"
            "• transférez automatiquement du contenu entre vos chats ;\n"
            "• consultez les livraisons et statistiques.\n\n"
            "Tout se configure depuis Telegram. Choisissez une option pour commencer."
        ),
    },
    "de": {
        "create_post": "Beitrag erstellen",
        "content_plan": "Inhaltsplan",
        "templates": "Vorlagen",
        "welcomes": "Begrüßungen",
        "farewells": "Verabschiedungen",
        "autocomplete": "Automatischer Text",
        "signatures": "Signaturen",
        "join_filters": "Beitrittsfilter",
        "relay": "Weiterleitung",
        "history": "Verlauf",
        "chats": "Kanäle und Gruppen",
        "stats": "Statistiken",
        "members": "Mitglieder",
        "language": "Sprache",
        "back_home": "Hauptmenü",
        "home_title": "Administrationsbereich",
        "home_prompt": "Was möchtest du tun?",
        "cancelled": "Vorgang abgebrochen.",
        "language_title": "Sprache der Oberfläche",
        "language_prompt": "Wähle die Sprache für diesen Arbeitsbereich.",
        "language_saved": "Sprache auf {language} geändert.",
        "start": (
            "👋 <b>Willkommen bei {workspace}</b>\n\n"
            "Verwalte deine Kanäle und Gruppen an einem Ort:\n\n"
            "• Beiträge erstellen, planen und wiederholen;\n"
            "• Vorlagen wiederverwenden und Inhalte organisieren;\n"
            "• Begrüßungen, Signaturen, Filter und Mitglieder konfigurieren;\n"
            "• Inhalte automatisch zwischen Chats weiterleiten;\n"
            "• Zustellungen und Statistiken prüfen.\n\n"
            "Alles wird in Telegram eingerichtet. Wähle eine Option."
        ),
    },
    "it": {
        "create_post": "Crea pubblicazione",
        "content_plan": "Piano contenuti",
        "templates": "Modelli",
        "welcomes": "Benvenuti",
        "farewells": "Messaggi di addio",
        "autocomplete": "Testo automatico",
        "signatures": "Firme",
        "join_filters": "Filtri di accesso",
        "relay": "Inoltro",
        "history": "Cronologia",
        "chats": "Canali e gruppi",
        "stats": "Statistiche",
        "members": "Membri",
        "language": "Lingua",
        "back_home": "Menu principale",
        "home_title": "Pannello di amministrazione",
        "home_prompt": "Cosa vuoi fare?",
        "cancelled": "Operazione annullata.",
        "language_title": "Lingua dell’interfaccia",
        "language_prompt": "Seleziona la lingua per questo spazio di lavoro.",
        "language_saved": "Lingua cambiata in {language}.",
        "start": (
            "👋 <b>Benvenuto in {workspace}</b>\n\n"
            "Gestisci canali e gruppi da un unico posto:\n\n"
            "• crea, programma e ripeti le pubblicazioni;\n"
            "• riutilizza modelli e organizza il piano contenuti;\n"
            "• configura benvenuti, firme, filtri e membri;\n"
            "• inoltra automaticamente contenuti tra le chat;\n"
            "• consulta consegne e statistiche.\n\n"
            "Tutto si configura da Telegram. Scegli un’opzione per iniziare."
        ),
    },
    "ru": {
        "create_post": "Создать публикацию",
        "content_plan": "Контент-план",
        "templates": "Шаблоны",
        "welcomes": "Приветствия",
        "farewells": "Прощания",
        "autocomplete": "Автотекст",
        "signatures": "Подписи",
        "join_filters": "Фильтры вступления",
        "relay": "Пересылка",
        "history": "История",
        "chats": "Каналы и группы",
        "stats": "Статистика",
        "members": "Участники",
        "language": "Язык",
        "back_home": "Главное меню",
        "home_title": "Панель управления",
        "home_prompt": "Что вы хотите сделать?",
        "cancelled": "Операция отменена.",
        "language_title": "Язык интерфейса",
        "language_prompt": "Выберите язык этого рабочего пространства.",
        "language_saved": "Выбран язык: {language}.",
        "start": (
            "👋 <b>Добро пожаловать в {workspace}</b>\n\n"
            "Управляйте каналами и группами в одном месте:\n\n"
            "• создавайте и планируйте публикации;\n"
            "• используйте шаблоны и контент-план;\n"
            "• настраивайте приветствия, подписи, фильтры и участников;\n"
            "• автоматически пересылайте контент между чатами;\n"
            "• просматривайте доставки и статистику.\n\n"
            "Все настраивается в Telegram. Выберите действие."
        ),
    },
    "ar": {
        "create_post": "إنشاء منشور",
        "content_plan": "خطة المحتوى",
        "templates": "القوالب",
        "welcomes": "رسائل الترحيب",
        "farewells": "رسائل الوداع",
        "autocomplete": "النص التلقائي",
        "signatures": "التوقيعات",
        "join_filters": "فلاتر الانضمام",
        "relay": "إعادة التوجيه",
        "history": "السجل",
        "chats": "القنوات والمجموعات",
        "stats": "الإحصاءات",
        "members": "الأعضاء",
        "language": "اللغة",
        "back_home": "القائمة الرئيسية",
        "home_title": "لوحة الإدارة",
        "home_prompt": "ماذا تريد أن تفعل؟",
        "cancelled": "تم إلغاء العملية.",
        "language_title": "لغة الواجهة",
        "language_prompt": "اختر لغة مساحة العمل هذه.",
        "language_saved": "تم تغيير اللغة إلى {language}.",
        "start": (
            "👋 <b>مرحبًا بك في {workspace}</b>\n\n"
            "أدر قنواتك ومجموعاتك من مكان واحد:\n\n"
            "• أنشئ المنشورات وجدولها وكررها؛\n"
            "• أعد استخدام القوالب ونظم خطة المحتوى؛\n"
            "• اضبط الترحيب والتوقيعات والفلاتر والأعضاء؛\n"
            "• أعد توجيه المحتوى تلقائيًا بين المحادثات؛\n"
            "• راجع عمليات التسليم والإحصاءات.\n\n"
            "يتم إعداد كل شيء من Telegram. اختر خيارًا للبدء."
        ),
    },
    "hi": {
        "create_post": "पोस्ट बनाएँ",
        "content_plan": "कंटेंट योजना",
        "templates": "टेम्पलेट",
        "welcomes": "स्वागत संदेश",
        "farewells": "विदाई संदेश",
        "autocomplete": "स्वचालित टेक्स्ट",
        "signatures": "हस्ताक्षर",
        "join_filters": "जॉइन फ़िल्टर",
        "relay": "फ़ॉरवर्डिंग",
        "history": "इतिहास",
        "chats": "चैनल और समूह",
        "stats": "आँकड़े",
        "members": "सदस्य",
        "language": "भाषा",
        "back_home": "मुख्य मेनू",
        "home_title": "प्रशासन पैनल",
        "home_prompt": "आप क्या करना चाहते हैं?",
        "cancelled": "कार्य रद्द किया गया।",
        "language_title": "इंटरफ़ेस भाषा",
        "language_prompt": "इस कार्यक्षेत्र की भाषा चुनें।",
        "language_saved": "भाषा {language} में बदल दी गई।",
        "start": (
            "👋 <b>{workspace} में आपका स्वागत है</b>\n\n"
            "अपने चैनल और समूह एक ही जगह से प्रबंधित करें:\n\n"
            "• पोस्ट बनाएँ, शेड्यूल करें और दोहराएँ;\n"
            "• टेम्पलेट और कंटेंट योजना का उपयोग करें;\n"
            "• स्वागत, हस्ताक्षर, फ़िल्टर और सदस्य सेट करें;\n"
            "• चैट के बीच सामग्री अपने-आप फ़ॉरवर्ड करें;\n"
            "• डिलीवरी और आँकड़े देखें।\n\n"
            "सब कुछ Telegram से सेट होता है। शुरू करने के लिए विकल्प चुनें।"
        ),
    },
    "zh": {
        "create_post": "创建帖子",
        "content_plan": "内容计划",
        "templates": "模板",
        "welcomes": "欢迎消息",
        "farewells": "告别消息",
        "autocomplete": "自动文本",
        "signatures": "签名",
        "join_filters": "加入筛选",
        "relay": "转发",
        "history": "历史记录",
        "chats": "频道和群组",
        "stats": "统计",
        "members": "成员",
        "language": "语言",
        "back_home": "主菜单",
        "home_title": "管理面板",
        "home_prompt": "您想做什么？",
        "cancelled": "操作已取消。",
        "language_title": "界面语言",
        "language_prompt": "请选择此工作区的语言。",
        "language_saved": "语言已更改为{language}。",
        "start": (
            "👋 <b>欢迎使用 {workspace}</b>\n\n"
            "在一个地方管理您的频道和群组：\n\n"
            "• 创建、安排和重复发布帖子；\n"
            "• 重用模板并组织内容计划；\n"
            "• 设置欢迎消息、签名、筛选和成员；\n"
            "• 在聊天之间自动转发内容；\n"
            "• 查看发送结果和统计。\n\n"
            "所有设置都可在 Telegram 中完成。请选择一个选项开始。"
        ),
    },
    "ja": {
        "create_post": "投稿を作成",
        "content_plan": "コンテンツ計画",
        "templates": "テンプレート",
        "welcomes": "ウェルカム",
        "farewells": "お別れメッセージ",
        "autocomplete": "自動テキスト",
        "signatures": "署名",
        "join_filters": "参加フィルター",
        "relay": "転送",
        "history": "履歴",
        "chats": "チャンネルとグループ",
        "stats": "統計",
        "members": "メンバー",
        "language": "言語",
        "back_home": "メインメニュー",
        "home_title": "管理パネル",
        "home_prompt": "何をしますか？",
        "cancelled": "操作をキャンセルしました。",
        "language_title": "インターフェース言語",
        "language_prompt": "このワークスペースの言語を選択してください。",
        "language_saved": "言語を{language}に変更しました。",
        "start": (
            "👋 <b>{workspace} へようこそ</b>\n\n"
            "チャンネルとグループを一か所で管理できます：\n\n"
            "• 投稿の作成、予約、繰り返し；\n"
            "• テンプレートとコンテンツ計画の管理；\n"
            "• 歓迎、署名、フィルター、メンバーの設定；\n"
            "• チャット間のコンテンツ自動転送；\n"
            "• 配信結果と統計の確認。\n\n"
            "すべて Telegram から設定できます。項目を選択してください。"
        ),
    },
    "ko": {
        "create_post": "게시물 만들기",
        "content_plan": "콘텐츠 계획",
        "templates": "템플릿",
        "welcomes": "환영 메시지",
        "farewells": "작별 메시지",
        "autocomplete": "자동 텍스트",
        "signatures": "서명",
        "join_filters": "가입 필터",
        "relay": "전달",
        "history": "기록",
        "chats": "채널 및 그룹",
        "stats": "통계",
        "members": "멤버",
        "language": "언어",
        "back_home": "메인 메뉴",
        "home_title": "관리 패널",
        "home_prompt": "무엇을 하시겠습니까?",
        "cancelled": "작업이 취소되었습니다.",
        "language_title": "인터페이스 언어",
        "language_prompt": "이 작업 공간의 언어를 선택하세요.",
        "language_saved": "언어가 {language}(으)로 변경되었습니다.",
        "start": (
            "👋 <b>{workspace}에 오신 것을 환영합니다</b>\n\n"
            "채널과 그룹을 한 곳에서 관리하세요:\n\n"
            "• 게시물을 만들고 예약하고 반복합니다;\n"
            "• 템플릿과 콘텐츠 계획을 관리합니다;\n"
            "• 환영, 서명, 필터 및 멤버를 설정합니다;\n"
            "• 채팅 간 콘텐츠를 자동으로 전달합니다;\n"
            "• 전송 결과와 통계를 확인합니다.\n\n"
            "모든 설정은 Telegram에서 할 수 있습니다. 시작할 항목을 선택하세요."
        ),
    },
}

_current_language: ContextVar[str] = ContextVar("current_language", default="es")


def normalize_language(code: str | None) -> str:
    return code if code in LANGUAGE_BY_CODE else "es"


def current_language() -> str:
    return normalize_language(_current_language.get())


def set_current_language(code: str):
    return _current_language.set(normalize_language(code))


def tr(key: str, locale: str | None = None, **values) -> str:
    code = normalize_language(locale or current_language())
    template = TRANSLATIONS.get(code, TRANSLATIONS["es"]).get(
        key, TRANSLATIONS["es"].get(key, key)
    )
    return template.format(**values)


def current_language_option() -> LanguageOption:
    return LANGUAGE_BY_CODE[current_language()]


class LocaleMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        from .database import SessionFactory
        from .repository import get_workspace

        language = "es"
        user = data.get("event_from_user")
        if user is not None:
            try:
                async with SessionFactory() as session:
                    workspace = await get_workspace(session, user.id)
                    if workspace is not None:
                        language = workspace.language_code
            except SQLAlchemyError as exc:
                logger.warning("Could not load interface language: %s", exc)
        token = set_current_language(language)
        try:
            return await handler(event, data)
        finally:
            _current_language.reset(token)
