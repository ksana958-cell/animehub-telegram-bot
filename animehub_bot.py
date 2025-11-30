from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    Defaults,
    ConversationHandler,
    MessageHandler,
    filters,
)
import json
import os
import random
import time

CONFIG = {
    "BOT_TOKEN": "8595192008:AAFUokx5z42w-lMmlxVqrzW43tpu0U1mOGA",
    "CHANNEL_USERNAME": "@AnimeHUB_Dream",
    "DATA_FILE": "bot_data.json",
    "ADMINS": [813738453],
}

BOT_TOKEN = CONFIG["BOT_TOKEN"]
CHANNEL_USERNAME = CONFIG["CHANNEL_USERNAME"]
DATA_FILE = CONFIG["DATA_FILE"]
ADMINS = CONFIG["ADMINS"]

ACCESS_LEVELS = {
    "free": 0,
    "friend": 1,
    "vip": 2,
}

SECTION_ACCESS = {
    "titles": "free",
    "hot_now": "free",
    "top150": "free",
    "movies": "friend",
}

RATE_LIMIT = {}
HEAVY_ACTIVE = 0
HEAVY_MAX = 10

TITLES = [
    {
        "id": "solo_leveling",
        "name": "Поднятие уровня в одиночку",
        "season": "Сезоны 1–2",
        "status": "Вышел",
        "episodes": "25 эпизодов",
        "year": "2024–2025",
        "studio": "A-1 Pictures",
        "author": "Chugong",
        "director": "Ясунори Одзаки",
        "voice": "AniDub / Crunchyroll",
        "shiki": "8.45",
        "imdb": "8.2",
        "kp": "8.0",
        "genres": "#Экшен #Фэнтези #Система #Охотники #Демоны",
        "playlist": "Сезоны 1–2 — смотреть можно в специальной комнате канала.",
        "desc": (
            "Сон Джин-Ву — охотник ранга E, которого считали самым слабым в мире. "
            "Он рискует жизнью в подземельях ради больной матери, пока однажды не получает "
            "уникальную «систему» прокачки, позволяющую расти в силе как в игре.\n\n"
            "В первых сезонах он проходит путь от бесполезного аутсайдера до охотника, "
            "чья мощь пугает даже самых опытных бойцов. Его ждут новые измерения, опасные "
            "рейды, интриги мира охотников и всё более мрачные тайны, связанные с его "
            "собственным предназначением."
        ),
        "top150": True,
        "min_access": "free",
    },
]

SECTION_TEXTS = {
    "titles": (
        "📚 Раздел «Аниме по тайтлам»\n\n"
        "Здесь будет удобный список всех тайтлов, доступных в AnimeHUB | Dream.\n"
        "Тайтлы можно разбить по алфавиту, сезонам или плейлистам.\n\n"
        "Открой навигацию в канале и переходи к нужному аниме."
    ),
    "hot_now": (
        "🔥 Раздел «Популярно сейчас»\n\n"
        "Текущие самые просматриваемые и обсуждаемые тайтлы на канале.\n"
        "Здесь могут появляться новые релизы и рекомендации на основе активности.\n\n"
        "Следи за обновлениями в AnimeHUB | Dream."
    ),
    "top150": (
        "🏆 Раздел «150 лучших аниме»\n\n"
        "Раздел основан на постере «150 лучших аниме».\n"
        "Постепенно все тайтлы с постера будут появляться в канале в высоком качестве.\n\n"
        "Используй канал как онлайн-версию постера и отмечай для себя уже просмотренное."
    ),
    "movies": (
        "🎬 Раздел «Полнометражки»\n\n"
        "Отдельный список аниме-фильмов: полнометражные продолжения, спин-оффы,\n"
        "самостоятельные истории и классика формата movie.\n\n"
        "Полнометражки будут вынесены в отдельные плейлисты в канале."
    ),
}

ACCESS_CODES = {
    "AHVIP2025": "vip",
    "AHFRIENDS": "friend",
}


def default_data():
    return {
        "version": 1,
        "users": {},
        "stats": {
            "sections": {},
            "random_used": 0,
            "started": 0,
            "posts_created": 0,
            "posts_edited": 0,
            "drafts_created": 0,
            "reposts": 0,
        },
        "friend_requests": {},
        "posts": {},
        "banned": {},
        "admins": ADMINS[:],
    }


def load_data():
    if not os.path.exists(DATA_FILE):
        return default_data()
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        broken_name = DATA_FILE + f".broken_{int(time.time())}"
        try:
            os.replace(DATA_FILE, broken_name)
        except OSError:
            pass
        return default_data()

    base = default_data()
    for k, v in base.items():
        if k not in data:
            data[k] = v
    if "sections" not in data["stats"]:
        data["stats"]["sections"] = {}
    for key in ["random_used", "started", "posts_created", "posts_edited", "drafts_created", "reposts"]:
        if key not in data["stats"]:
            data["stats"][key] = 0
    if "friend_requests" not in data:
        data["friend_requests"] = {}
    if "users" not in data:
        data["users"] = {}
    if "posts" not in data:
        data["posts"] = {}
    if "banned" not in data:
        data["banned"] = {}
    if "version" not in data:
        data["version"] = 1
    if "admins" not in data:
        data["admins"] = ADMINS[:]
    return data


def save_data(data):
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)


def get_user(data, user_id):
    uid = str(user_id)
    if uid not in data["users"]:
        data["users"][uid] = {
            "access": "free",
            "favorites": [],
            "watched_150": [],
            "friends": [],
            "activated": False,
            "created_at": int(time.time()),
            "username": None,
            "full_name": None,
        }
    else:
        u = data["users"][uid]
        if "favorites" not in u:
            u["favorites"] = []
        if "watched_150" not in u:
            u["watched_150"] = []
        if "friends" not in u:
            u["friends"] = []
        if "access" not in u:
            u["access"] = "free"
        if "activated" not in u:
            u["activated"] = False
        if "created_at" not in u:
            u["created_at"] = int(time.time())
        if "username" not in u:
            u["username"] = None
        if "full_name" not in u:
            u["full_name"] = None

    user = data["users"][uid]
    return user


def update_user_names(data, user_id, tg_user):
    user = get_user(data, user_id)
    username = tg_user.username if tg_user else None
    full_name = None
    if tg_user:
        if tg_user.last_name:
            full_name = f"{tg_user.first_name} {tg_user.last_name}"
        else:
            full_name = tg_user.first_name
    user["username"] = username
    user["full_name"] = full_name


def inc_section_stat(data, section):
    sec = data["stats"]["sections"]
    sec[section] = sec.get(section, 0) + 1


def has_access(user_data, required_level: str) -> bool:
    user_level = user_data.get("access", "free")
    return ACCESS_LEVELS.get(user_level, 0) >= ACCESS_LEVELS.get(required_level, 0)


def is_admin(data, user_id: int) -> bool:
    admins_from_data = set(data.get("admins", []))
    base_admins = set(ADMINS)
    return user_id in admins_from_data or user_id in base_admins


def is_root_admin(user_id: int) -> bool:
    return user_id in ADMINS


async def is_subscribed(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False


def check_rate_limit(user_id: int, key: str, interval: float) -> bool:
    now = time.time()
    last = RATE_LIMIT.get((user_id, key), 0)
    if now - last < interval:
        return True
    RATE_LIMIT[(user_id, key)] = now
    return False


def is_user_banned(data, user_id: int) -> bool:
    return data.get("banned", {}).get(str(user_id), False)


async def abort_if_banned(update: Update, data) -> bool:
    user_id = update.effective_user.id
    if is_user_banned(data, user_id):
        if update.effective_message:
            await update.effective_message.reply_text("Ты заблокирован в этом боте.")
        return True
    return False


def build_main_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📚 Аниме по тайтлам", callback_data="sec_titles")],
        [InlineKeyboardButton("🔥 Популярно сейчас", callback_data="sec_hot_now")],
        [InlineKeyboardButton("🏆 150 лучших аниме", callback_data="sec_top150")],
        [InlineKeyboardButton("🎬 Полнометражки", callback_data="sec_movies")],
        [InlineKeyboardButton("🎲 Случайный тайтл", callback_data="rand_title")],
        [InlineKeyboardButton("👤 Мой профиль", callback_data="my_profile")],
        [
            InlineKeyboardButton(
                "🏠 Открыть канал",
                url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}",
            )
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_section_keyboard(section: str | None = None) -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")]
    if section in ("titles", "hot_now", "top150", "movies"):
        row.append(
            InlineKeyboardButton(
                "🏠 Открыть канал",
                url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}",
            )
        )
    keyboard = [row]
    return InlineKeyboardMarkup(keyboard)


def build_title_keyboard(title_id: str, user_data: dict) -> InlineKeyboardMarkup:
    favs = user_data.get("favorites", [])
    if title_id in favs:
        text = "⭐ Убрать из избранного"
        cb = f"fav_remove:{title_id}"
    else:
        text = "⭐ В избранное"
        cb = f"fav_add:{title_id}"
    keyboard = [
        [InlineKeyboardButton(text, callback_data=cb)],
        [InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_premium_card(title: dict) -> str:
    access = title.get("min_access", "free")
    access_label = {
        "free": "Открыт для всех",
        "friend": "Доступ для друзей",
        "vip": "VIP-доступ",
    }.get(access, "Ограниченный доступ")

    return (
        f"🎬 ⭐ <b>{title['name']}</b>\n"
        f"{title.get('season', 'Сезон 1')} · ТВ-сериал\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📌 <b>Информация</b>\n"
        f"📅 Статус: {title.get('status', 'Вышел')}\n"
        f"🎞 Эпизодов: {title.get('episodes', '??')}\n"
        f"📆 Год: {title.get('year', '----')}\n"
        f"🏢 Студия: {title.get('studio', '-')}\n"
        f"✍ Автор: {title.get('author', '-')}\n"
        f"🎬 Режиссёр: {title.get('director', '-')}\n"
        f"🔊 Озвучки: {title.get('voice', '-')}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📊 <b>Рейтинги</b>\n"
        f"📈 Shikimori: {title.get('shiki', '-')}\n"
        f"🍿 IMDb: {title.get('imdb', '-')}\n"
        f"🎥 Кинопоиск: {title.get('kp', '-')}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🏷 <b>Жанры</b>\n"
        f"{title.get('genres', '-')}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📂 <b>Сезоны / Плейлисты</b>\n"
        f"{title.get('playlist', 'Ссылка на плейлист появится позже')}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📝 <b>Описание</b>\n"
        f"{title.get('desc', '-')}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔑 Доступ: {access_label}\n\n"
        "💠 <b>AnimeHUB | Dream — 4K Upscale Edition</b>\n"
        "Доступно улучшенное качество до 4K.\n\n"
        "⭐ Добавить в избранное → @AnimeHubDreamBot\n"
    )


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, data) -> None:
    data["stats"]["started"] += 1
    save_data(data)
    text = (
        "👋 Привет! Это навигационный бот канала AnimeHUB | Dream.\n\n"
        "Я помогаю ориентироваться в аниме-архиве:\n"
        "• 📚 «Аниме по тайтлам»\n"
        "• 🔥 «Популярно сейчас»\n"
        "• 🏆 «150 лучших аниме»\n"
        "• 🎬 «Полнометражки»\n\n"
        "Выбери раздел из меню ниже."
    )
    reply_markup = build_main_menu_keyboard()
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)


async def send_section(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    data,
    section_key: str,
    from_callback: bool,
) -> None:
    user_id = update.effective_user.id
    tg_user = update.effective_user
    user_data = get_user(data, user_id)
    update_user_names(data, user_id, tg_user)

    required_access = SECTION_ACCESS.get(section_key)
    if required_access and not has_access(user_data, required_level=required_access):
        text = (
            "🔑 Доступ к этому разделу ограничен.\n\n"
            f"Нужен уровень: <b>{required_access}</b>\n"
            f"Твой уровень сейчас: <b>{user_data.get('access', 'free')}</b>\n\n"
            "Если у тебя есть код доступа, введи его командой:\n"
            "/code &lt;код&gt;"
        )
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")]]
        )
        if from_callback:
            await update.callback_query.edit_message_text(text, reply_markup=kb)
        else:
            await update.effective_message.reply_text(text, reply_markup=kb)
        save_data(data)
        return

    inc_section_stat(data, section_key)
    save_data(data)

    if section_key in ("top150", "movies"):
        subscribed = await is_subscribed(context, user_id)
        if not subscribed:
            text = (
                "🔒 Этот раздел доступен только подписчикам канала AnimeHUB | Dream.\n\n"
                "Подпишись на канал, затем вернись сюда и открой раздел ещё раз."
            )
            kb = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "✅ Открыть канал",
                            url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}",
                        )
                    ],
                    [InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")],
                ]
            )
            if from_callback:
                await update.callback_query.edit_message_text(text, reply_markup=kb)
            else:
                await update.effective_message.reply_text(text, reply_markup=kb)
            return

    text = SECTION_TEXTS.get(section_key, "Раздел временно недоступен.")
    kb = build_section_keyboard(section_key)
    if from_callback:
        await update.callback_query.edit_message_text(text, reply_markup=kb)
    else:
        await update.effective_message.reply_text(text, reply_markup=kb)


async def send_random_title(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    data,
    from_callback: bool,
) -> None:
    user_id = update.effective_user.id
    if check_rate_limit(user_id, "rand_title", 2.0):
        if from_callback and update.callback_query:
            await update.callback_query.answer("Слишком часто, попробуй позже.", show_alert=False)
        else:
            await update.effective_message.reply_text("Слишком часто крутишь рандом, попробуй чуть позже.")
        return

    tg_user = update.effective_user
    user_data = get_user(data, user_id)
    update_user_names(data, user_id, tg_user)

    available = []
    for t in TITLES:
        required = t.get("min_access", "free")
        if has_access(user_data, required):
            available.append(t)
    if not available:
        text = (
            "Сейчас для твоего уровня доступа нет тайтлов для случайного выбора.\n\n"
            "Если у тебя есть код доступа, активируй его командой:\n"
            "/code &lt;код&gt;"
        )
        if from_callback:
            await update.callback_query.edit_message_text(text)
        else:
            await update.effective_message.reply_text(text)
        return

    data["stats"]["random_used"] += 1
    save_data(data)
    title = random.choice(available)
    text = f"🎲 Случайный тайтл:\n\n⭐ {title['name']}\n\n{title['desc']}"
    kb = build_title_keyboard(title["id"], user_data)
    if from_callback:
        await update.callback_query.edit_message_text(text, reply_markup=kb)
    else:
        await update.effective_message.reply_text(text, reply_markup=kb)


async def show_profile(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    data,
    from_callback: bool,
) -> None:
    user_id = update.effective_user.id
    tg_user = update.effective_user
    user_data = get_user(data, user_id)
    update_user_names(data, user_id, tg_user)

    fav_count = len(user_data.get("favorites", []))
    watched_150 = len(user_data.get("watched_150", []))
    friends_count = len(user_data.get("friends", []))
    access = user_data.get("access", "free")

    total_top150 = sum(1 for t in TITLES if t.get("top150"))
    progress = ""
    if total_top150 > 0:
        percent = round(watched_150 / total_top150 * 100, 1)
        progress = f" ({watched_150}/{total_top150}, {percent}%)"

    name_part = user_data.get("full_name") or tg_user.first_name
    text = (
        f"👤 Профиль: <b>{name_part}</b>\n\n"
        f"🔑 Уровень доступа: <b>{access}</b>\n"
        f"⭐ Избранных тайтлов: <b>{fav_count}</b>\n"
        f"🏆 Прогресс по «150 лучшим аниме»: <b>{watched_150}</b>{progress}\n"
        f"🤝 Друзей: <b>{friends_count}</b>\n\n"
        "Используй разделы бота, чтобы находить новые аниме и добавлять их в избранное."
    )
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⭐ Мои избранные", callback_data="prof_favorites")],
            [InlineKeyboardButton("🏆 Мой прогресс 150", callback_data="prof_top150")],
            [InlineKeyboardButton("🤝 Мои друзья", callback_data="prof_friends")],
            [InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")],
        ]
    )
    if from_callback:
        await update.callback_query.edit_message_text(text, reply_markup=kb)
    else:
        await update.effective_message.reply_text(text, reply_markup=kb)


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    tg_user = update.effective_user
    user_data = get_user(data, user_id)
    update_user_names(data, user_id, tg_user)
    save_data(data)

    args = context.args
    if args and args[0].strip().lower() == "activate":
        user_data["activated"] = True
        save_data(data)
        text = (
            "⚡ Профиль активирован!\n\n"
            f"Твой Telegram ID: <code>{user_id}</code>\n\n"
            "Теперь ты можешь:\n"
            "• Добавлять друзей: /friend_invite &lt;ID&gt;\n"
            "• Смотреть входящие заявки: /friend_requests\n"
            "• Список друзей: /friend_list\n\n"
            "Нажми кнопку ниже, чтобы открыть главное меню."
        )
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("📚 Открыть главное меню", callback_data="main_menu")]]
        )
        await update.effective_message.reply_text(text, reply_markup=kb)
        return

    if not user_data.get("activated", False):
        text = (
            "⚡ Перед началом нужно активировать профиль.\n\n"
            "Это свяжет твой Telegram-аккаунт с прогрессом в AnimeHUB | Dream.\n\n"
            "Нажми кнопку ниже, чтобы активировать профиль."
        )
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("⚡ Активировать профиль", callback_data="activate_profile")]]
        )
        await update.effective_message.reply_text(text, reply_markup=kb)
        return

    await show_main_menu(update, context, data)


async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if await abort_if_banned(update, data):
        return
    await show_main_menu(update, context, data)


async def handle_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    tg_user = update.effective_user
    user_data = get_user(data, user_id)
    update_user_names(data, user_id, tg_user)

    if not context.args:
        await update.effective_message.reply_text(
            "Введите код после команды, например:\n/code AHVIP2025"
        )
        return
    code = context.args[0].strip()
    level = ACCESS_CODES.get(code)
    if not level:
        await update.effective_message.reply_text("❌ Неверный или устаревший код доступа.")
        return
    user_data["access"] = level
    save_data(data)
    await update.effective_message.reply_text(f"✅ Код принят. Новый уровень доступа: {level}")


async def handle_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if await abort_if_banned(update, data):
        return
    await show_profile(update, context, data, from_callback=False)


async def handle_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    if not is_admin(data, user_id):
        await update.effective_message.reply_text("Эта команда доступна только администратору.")
        return
    users_count = len(data["users"])
    sections = data["stats"]["sections"]
    parts = [
        f"👥 Пользователей в базе: {users_count}",
        f"🎲 Случайный тайтл использован: {data['stats']['random_used']} раз",
        f"▶ Постов создано через /post: {data['stats']['posts_created']}",
        f"📝 Постов отредактировано через /edit_post: {data['stats']['posts_edited']}",
        f"🧾 Черновиков через /post_draft: {data['stats']['drafts_created']}",
        f"🔁 Репостов через /repost: {data['stats']['reposts']}",
        "📊 Переходы по разделам:",
    ]
    for k, v in sections.items():
        parts.append(f"• {k}: {v}")
    text = "\n".join(parts)
    await update.effective_message.reply_text(text)


async def handle_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    if not is_admin(data, user_id):
        await update.effective_message.reply_text("Эта команда доступна только администратору.")
        return

    users = data.get("users", {})
    activated_users = [(uid, u) for uid, u in users.items() if u.get("activated")]
    total = len(activated_users)

    if total == 0:
        await update.effective_message.reply_text("Пока нет ни одного активированного пользователя.")
        return

    lines = [f"👥 Активированные пользователи: {total}"]
    for uid, u in activated_users:
        name = u.get("full_name") or f"Пользователь {uid}"
        lines.append(f"• <a href='tg://user?id={uid}'>{name}</a>")
    text = "\n".join(lines)
    await update.effective_message.reply_text(text)


async def handle_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    tg_user = update.effective_user
    user_data = get_user(data, user_id)
    update_user_names(data, user_id, tg_user)
    save_data(data)

    favs = user_data.get("favorites", [])
    if not favs:
        await update.effective_message.reply_text(
            "У тебя пока нет избранных тайтлов.\n"
            "Открой карточку тайтла и нажми «⭐ В избранное»."
        )
        return

    lines = ["⭐ Твои избранные тайтлы:"]
    for fid in favs:
        t = next((t for t in TITLES if t["id"] == fid), None)
        if t:
            lines.append(f"• <b>{t['name']}</b> — /title {t['id']}")
        else:
            lines.append(f"• Неизвестный тайтл: {fid}")
    text = "\n".join(lines)
    await update.effective_message.reply_text(text)


async def handle_watched_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    tg_user = update.effective_user
    user_data = get_user(data, user_id)
    update_user_names(data, user_id, tg_user)

    if not context.args:
        await update.effective_message.reply_text(
            "Использование:\n/watched_add <id тайтла>\n\nНапример:\n/watched_add solo_leveling"
        )
        return
    tid = context.args[0].strip().lower()
    title = next((t for t in TITLES if t["id"] == tid), None)
    if not title:
        await update.effective_message.reply_text("❌ Тайтл с таким ID не найден.")
        return

    if title.get("top150"):
        watched = user_data.get("watched_150", [])
        if tid not in watched:
            watched.append(tid)
            user_data["watched_150"] = watched
            save_data(data)
            await update.effective_message.reply_text(
                f"🏆 Тайтл «{title['name']}» отмечен как просмотренный из «150 лучших аниме»."
            )
        else:
            await update.effective_message.reply_text(
                f"Этот тайтл уже отмечен как просмотренный в списке «150 лучших аниме»."
            )
    else:
        await update.effective_message.reply_text(
            "Этот тайтл сейчас не помечен как часть списка «150 лучших аниме».\n"
            "Но ты всё равно можешь следить за прогрессом по постеру вручную."
        )


async def handle_watched_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    tg_user = update.effective_user
    user_data = get_user(data, user_id)
    update_user_names(data, user_id, tg_user)

    if not context.args:
        await update.effective_message.reply_text(
            "Использование:\n/watched_remove <id тайтла>\n\nНапример:\n/watched_remove solo_leveling"
        )
        return
    tid = context.args[0].strip().lower()
    watched = user_data.get("watched_150", [])
    if tid in watched:
        watched.remove(tid)
        user_data["watched_150"] = watched
        save_data(data)
        await update.effective_message.reply_text("Тайтл убран из прогресса по «150 лучшим аниме».")
    else:
        await update.effective_message.reply_text("Этот тайтл не отмечен как просмотренный в 150.")


async def handle_watched_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    tg_user = update.effective_user
    user_data = get_user(data, user_id)
    update_user_names(data, user_id, tg_user)

    watched = user_data.get("watched_150", [])
    total_top150 = sum(1 for t in TITLES if t.get("top150"))
    if not watched:
        msg = "Ты пока не отметил ни одного тайтла из «150 лучших аниме»."
        if total_top150 > 0:
            msg += "\n\nДобавь просмотренный тайтл командой:\n/watched_add <id>"
        await update.effective_message.reply_text(msg)
        return

    lines = ["🏆 Твои просмотренные тайтлы из «150 лучших аниме»:"]

    for tid in watched:
        t = next((t for t in TITLES if t["id"] == tid), None)
        if t:
            lines.append(f"• <b>{t['name']}</b> — /title {t['id']}")
        else:
            lines.append(f"• Неизвестный тайтл: {tid}")

    if total_top150 > 0:
        percent = round(len(watched) / total_top150 * 100, 1)
        lines.append(f"\nПрогресс: {len(watched)}/{total_top150} ({percent}%)")

    text = "\n".join(lines)
    await update.effective_message.reply_text(text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    if is_admin(data, user_id):
        text = (
            "🛠 <b>Команды для админа</b>\n\n"
            "/start – запустить бота\n"
            "/menu – открыть главное меню навигации\n"
            "/help – показать это меню помощи\n"
            "/title &lt;id&gt; – показать карточку тайтла\n"
            "/code &lt;код&gt; – ввести код доступа\n"
            "/profile – мой профиль\n"
            "/favorites – список избранных тайтлов\n"
            "/watched_add &lt;id&gt; – добавить тайтл в прогресс по 150\n"
            "/watched_remove &lt;id&gt; – убрать тайтл из прогресса по 150\n"
            "/watched_list – показать прогресс по 150\n"
            "/myid – показать мой Telegram ID\n"
            "/friend_invite &lt;ID&gt; – добавить друга\n"
            "/friend_requests – входящие заявки в друзья\n"
            "/friend_accept &lt;ID&gt; – принять заявку\n"
            "/friend_list – список друзей\n"
            "/friend_vs &lt;ID&gt; – сравнить прогресс с другом\n"
            "/post – мастер создания поста в канал\n"
            "/post_draft – создать черновик поста с подтверждением\n"
            "/edit_post &lt;ссылка или ID&gt; – изменить уже опубликованный пост\n"
            "/link_post &lt;ссылка/ID&gt; &lt;title_id&gt; – привязать пост к тайтлу\n"
            "/repost &lt;ссылка или ID&gt; – пересоздать пост в канале\n"
            "/stats – статистика использования бота\n"
            "/users – список всех активированных пользователей\n"
            "/ban_user &lt;ID&gt; – заблокировать пользователя в боте\n"
            "/unban_user &lt;ID&gt; – разблокировать пользователя\n"
            "/admin_list – список админов\n"
            "/add_admin &lt;ID&gt; – добавить админа (только корневой)\n"
            "/remove_admin &lt;ID&gt; – убрать админа (кроме корневых)\n\n"
            "Основная навигация по аниме — через кнопки под сообщениями."
        )
    else:
        text = (
            "📖 <b>Команды для пользователя</b>\n\n"
            "/start – запустить бота и активировать профиль\n"
            "/menu – открыть главное меню навигации\n"
            "/help – показать это меню помощи\n"
            "/title &lt;id&gt; – показать карточку тайтла\n"
            "/code &lt;код&gt; – ввести код доступа (если он есть)\n"
            "/profile – мой профиль в боте\n"
            "/favorites – мои избранные тайтлы\n"
            "/watched_add &lt;id&gt; – отметить тайтл как просмотренный из 150\n"
            "/watched_remove &lt;id&gt; – убрать тайтл из прогресса по 150\n"
            "/watched_list – показать мой прогресс по 150\n"
            "/myid – показать мой Telegram ID\n"
            "/friend_invite &lt;ID&gt; – отправить приглашение в друзья\n"
            "/friend_requests – входящие заявки в друзья\n"
            "/friend_accept &lt;ID&gt; – принять заявку\n"
            "/friend_list – список друзей\n"
            "/friend_vs &lt;ID&gt; – сравнить прогресс по аниме с другом\n\n"
            "Основная навигация по аниме доступна через кнопки под сообщениями: "
            "тайтлы, популярное, 150 лучших, полнометражки."
        )
    await update.effective_message.reply_text(text)


async def handle_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    tg_user = update.effective_user
    user_data = get_user(data, user_id)
    update_user_names(data, user_id, tg_user)

    if not context.args:
        await update.effective_message.reply_text(
            "Использование:\n/title <id>\n\n"
            "Примеры:\n"
            "/title solo_leveling\n"
            "/title death_note\n"
            "/title made_in_abyss"
        )
        return

    tid = context.args[0].strip().lower()
    title = next((t for t in TITLES if t["id"] == tid), None)
    if not title:
        await update.effective_message.reply_text("❌ Тайтл с таким ID не найден.")
        return

    required = title.get("min_access", "free")
    if not has_access(user_data, required):
        await update.effective_message.reply_text(
            "🔑 Этот тайтл доступен не для всех.\n\n"
            f"Нужен уровень: <b>{required}</b>\n"
            f"Твой уровень сейчас: <b>{user_data.get('access', 'free')}</b>\n\n"
            "Если у тебя есть код доступа, введи его командой:\n"
            "/code &lt;код&gt;"
        )
        return

    card = build_premium_card(title)
    await update.effective_message.reply_text(card)


async def handle_myid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    text = (
        f"Твой Telegram ID: <code>{user_id}</code>\n\n"
        "Отправь его другу, чтобы он смог добавить тебя в друзья:\n"
        "/friend_invite "
        f"{user_id}"
    )
    await update.effective_message.reply_text(text)

async def handle_friend_invite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if await abort_if_banned(update, data):
        return

    from_id = update.effective_user.id
    if check_rate_limit(from_id, "friend_invite", 2.0):
        await update.effective_message.reply_text("Слишком часто отправляешь приглашения, попробуй позже.")
        return

    tg_user = update.effective_user
    from_user = get_user(data, from_id)
    update_user_names(data, from_id, tg_user)

    target_id = None
    if update.message and update.message.reply_to_message:
        reply_user = update.message.reply_to_message.from_user
        if reply_user and not reply_user.is_bot:
            target_id = reply_user.id

    if target_id is None:
        if not context.args:
            await update.effective_message.reply_text(
                "Использование:\n"
                "• Ответь на сообщение друга и набери: /friend_invite\n"
                "• Или: /friend_invite @username\n"
                "• Или: /friend_invite ссылка_на_профиль (например, https://t.me/username)\n"
                "• Или: /friend_invite <ID друга>\n\n"
                "ID друг может узнать командой /myid у себя."
            )
            return

        raw = context.args[0].strip()
        token = raw
        if "t.me/" in raw:
            part = raw.split("t.me/", 1)[1]
            for sep in ("?", "/"):
                if sep in part:
                    part = part.split(sep, 1)[0]
            token = part

        if token.startswith("@"):
            token = token[1:]

        if token.isdigit():
            target_id = int(token)
        else:
            try:
                chat = await context.bot.get_chat(f"@{token}")
                target_id = chat.id
            except Exception:
                await update.effective_message.reply_text(
                    "Не удалось найти пользователя по этому username/ссылке.\n"
                    "Убедись, что:\n"
                    "• друг уже написал что-то боту\n"
                    "• указан корректный @username или ссылка вида https://t.me/username"
                )
                return

    if target_id == from_id:
        await update.effective_message.reply_text("Нельзя добавить в друзья самого себя.")
        return

    get_user(data, target_id)

    from_uid = str(from_id)
    target_uid = str(target_id)

    if target_uid in from_user.get("friends", []):
        await update.effective_message.reply_text("Этот пользователь уже есть у тебя в друзьях.")
        return

    reqs = data.get("friend_requests", {})
    lst = reqs.get(target_uid, [])
    if from_uid in lst:
        await update.effective_message.reply_text("Приглашение этому пользователю уже отправлено.")
        return

    lst.append(from_uid)
    reqs[target_uid] = lst
    data["friend_requests"] = reqs
    save_data(data)

    await update.effective_message.reply_text(
        "✅ Приглашение в друзья отправлено.\n"
        "Скажи другу запустить бота и набрать /friend_requests, чтобы принять."
    )

    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=(
                "🤝 Тебе пришло приглашение в друзья!\n\n"
                f"От пользователя: <a href='tg://user?id={from_id}'>{from_id}</a>\n\n"
                "Чтобы посмотреть и принять приглашение, набери команду:\n"
                "/friend_requests"
            ),
        )
    except Exception:
        pass

async def handle_friend_requests(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    uid = str(user_id)
    reqs = data.get("friend_requests", {}).get(uid, [])
    if not reqs:
        await update.effective_message.reply_text("У тебя нет входящих приглашений в друзья.")
        return

    lines = ["📨 Входящие приглашения в друзья:"]
    for rid in reqs:
        lines.append(
            f"• <a href='tg://user?id={rid}'>Пользователь {rid}</a> — принять: "
            f"/friend_accept {rid}"
        )
    text = "\n".join(lines)
    await update.effective_message.reply_text(text)


async def handle_friend_accept(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    uid = str(user_id)

    if not context.args:
        await update.effective_message.reply_text(
            "Использование:\n/friend_accept <ID>\n\n"
            "Посмотри список входящих заявок: /friend_requests"
        )
        return
    try:
        other_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("ID должен быть числом.")
        return

    other_uid = str(other_id)
    reqs = data.get("friend_requests", {})
    lst = reqs.get(uid, [])

    if other_uid not in lst:
        await update.effective_message.reply_text("От этого пользователя нет активного приглашения.")
        return

    user_data = get_user(data, user_id)
    other_data = get_user(data, other_id)

    if other_uid not in user_data["friends"]:
        user_data["friends"].append(other_uid)
    if uid not in other_data["friends"]:
        other_data["friends"].append(uid)

    lst.remove(other_uid)
    if lst:
        reqs[uid] = lst
    else:
        reqs.pop(uid, None)
    data["friend_requests"] = reqs

    save_data(data)

    await update.effective_message.reply_text(
        f"✅ Пользователь {other_id} добавлен в друзья.\n"
        "Теперь вы можете сравнивать прогресс по аниме: /friend_vs "
        f"{other_id}"
    )


async def handle_friend_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    tg_user = update.effective_user
    user_data = get_user(data, user_id)
    update_user_names(data, user_id, tg_user)

    friends = user_data.get("friends", [])
    if not friends:
        await update.effective_message.reply_text(
            "У тебя пока нет друзей в боте.\n"
            "Отправь свой ID (/myid) другу и пусть он добавит тебя через /friend_invite."
        )
        return

    lines = ["🤝 Твой список друзей:"]
    for fid in friends:
        fdata = get_user(data, int(fid))
        name = fdata.get("full_name") or f"Пользователь {fid}"
        lines.append(f"• <a href='tg://user?id={fid}'>{name}</a>")
    lines.append("\nЧтобы сравнить прогресс, используй:\n/friend_vs <ID друга>")
    text = "\n".join(lines)
    await update.effective_message.reply_text(text)


async def handle_friend_vs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    if not context.args:
        await update.effective_message.reply_text(
            "Использование:\n/friend_vs <ID друга>\n\n"
            "Сначала посмотри список друзей: /friend_list"
        )
        return
    try:
        other_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("ID должен быть числом.")
        return

    uid = str(user_id)
    other_uid = str(other_id)

    user_data = get_user(data, user_id)
    other_data = get_user(data, other_id)

    if other_uid not in user_data.get("friends", []):
        await update.effective_message.reply_text(
            "Этот пользователь не в твоих друзьях.\n"
            "Сначала добавь его через систему заявок."
        )
        return

    u_fav = len(user_data.get("favorites", []))
    o_fav = len(other_data.get("favorites", []))
    u_150 = len(user_data.get("watched_150", []))
    o_150 = len(other_data.get("watched_150", []))

    if u_fav > o_fav:
        fav_result = "По количеству тайтлов (избранное) побеждаешь ты."
    elif u_fav < o_fav:
        fav_result = "По количеству тайтлов (избранное) пока лидирует твой друг."
    else:
        fav_result = "По количеству тайтлов в избранном у вас ничья."

    if u_150 > o_150:
        top_result = "По «150 лучшим аниме» побеждаешь ты."
    elif u_150 < o_150:
        top_result = "По «150 лучшим аниме» пока лидирует твой друг."
    else:
        top_result = "По «150 лучшим аниме» у вас ничья."

    text = (
        "⚔ Сравнение аниме-прогресса\n\n"
        f"Ты:\n"
        f"• Избранных тайтлов: {u_fav}\n"
        f"• Из «150 лучших аниме»: {u_150}\n\n"
        f"Друг ({other_id}):\n"
        f"• Избранных тайтлов: {o_fav}\n"
        f"• Из «150 лучших аниме»: {o_150}\n\n"
        f"{fav_result}\n"
        f"{top_result}"
    )
    await update.effective_message.reply_text(text)


async def handle_favorites_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await handle_favorites(update, context)


async def handle_top150_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await handle_watched_list(update, context)


async def handle_friends_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await handle_friend_list(update, context)


async def handle_ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    user_id = update.effective_user.id
    if not is_admin(data, user_id):
        await update.effective_message.reply_text("Эта команда только для админа.")
        return
    if not context.args:
        await update.effective_message.reply_text("Использование:\n/ban_user <ID>")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("ID должен быть числом.")
        return
    tid = str(target_id)
    banned = data.get("banned", {})
    banned[tid] = True
    data["banned"] = banned
    save_data(data)
    await update.effective_message.reply_text(f"Пользователь {target_id} заблокирован в боте.")


async def handle_unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    user_id = update.effective_user.id
    if not is_admin(data, user_id):
        await update.effective_message.reply_text("Эта команда только для админа.")
        return
    if not context.args:
        await update.effective_message.reply_text("Использование:\n/unban_user <ID>")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("ID должен быть числом.")
        return
    tid = str(target_id)
    banned = data.get("banned", {})
    if tid in banned:
        banned.pop(tid, None)
        data["banned"] = banned
        save_data(data)
        await update.effective_message.reply_text(f"Пользователь {target_id} разблокирован.")
    else:
        await update.effective_message.reply_text("Этот пользователь не был заблокирован.")


async def handle_admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    if not is_admin(data, user_id):
        await update.effective_message.reply_text("Эта команда только для админов.")
        return

    admins_file = set(data.get("admins", []))
    base_admins = set(ADMINS)
    all_admins = sorted(admins_file | base_admins)

    lines = ["🔐 Список админов:"]
    for aid in all_admins:
        mark = " (root)" if aid in base_admins else ""
        lines.append(f"• <a href='tg://user?id={aid}'>{aid}</a>{mark}")
    text = "\n".join(lines)
    await update.effective_message.reply_text(text)


async def handle_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    if not is_root_admin(user_id):
        await update.effective_message.reply_text("Добавлять админов может только корневой админ.")
        return
    if not context.args:
        await update.effective_message.reply_text("Использование:\n/add_admin <ID>")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("ID должен быть числом.")
        return

    admins_list = data.get("admins", [])
    if target_id in admins_list or target_id in ADMINS:
        await update.effective_message.reply_text("Этот пользователь уже админ.")
        return

    admins_list.append(target_id)
    data["admins"] = admins_list
    save_data(data)
    await update.effective_message.reply_text(f"Пользователь {target_id} добавлен в админы.")


async def handle_remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    if not is_root_admin(user_id):
        await update.effective_message.reply_text("Удалять админов может только корневой админ.")
        return
    if not context.args:
        await update.effective_message.reply_text("Использование:\n/remove_admin <ID>")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("ID должен быть числом.")
        return

    if target_id in ADMINS:
        await update.effective_message.reply_text("Нельзя удалить корневого админа из CONFIG.")
        return

    admins_list = data.get("admins", [])
    if target_id not in admins_list:
        await update.effective_message.reply_text("Этот пользователь не является админом (или только root через CONFIG).")
        return

    admins_list = [a for a in admins_list if a != target_id]
    data["admins"] = admins_list
    save_data(data)
    await update.effective_message.reply_text(f"Пользователь {target_id} убран из админов.")


async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if await abort_if_banned(update, data):
        return
    query = update.callback_query
    await query.answer()
    data_str = query.data

    user_id = update.effective_user.id
    tg_user = update.effective_user
    user_data = get_user(data, user_id)
    update_user_names(data, user_id, tg_user)
    save_data(data)

    if data_str == "activate_profile":
        user_data["activated"] = True
        save_data(data)
        text = (
            "⚡ Профиль активирован!\n\n"
            f"Твой Telegram ID: <code>{user_id}</code>\n\n"
            "Теперь ты можешь:\n"
            "• Добавлять друзей: /friend_invite &lt;ID&gt;\n"
            "• Смотреть входящие заявки: /friend_requests\n"
            "• Список друзей: /friend_list\n\n"
            "Нажми кнопку ниже, чтобы открыть главное меню."
        )
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("📚 Открыть главное меню", callback_data="main_menu")]]
        )
        await query.edit_message_text(text, reply_markup=kb)
        return

    if data_str == "main_menu":
        await show_main_menu(update, context, data)
        return

    if data_str.startswith("sec_"):
        section_key = data_str.replace("sec_", "", 1)
        await send_section(update, context, data, section_key, from_callback=True)
        return

    if data_str == "rand_title":
        await send_random_title(update, context, data, from_callback=True)
        return

    if data_str == "my_profile":
        await show_profile(update, context, data, from_callback=True)
        return

    if data_str == "prof_favorites":
        await handle_favorites(update, context)
        return

    if data_str == "prof_top150":
        await handle_watched_list(update, context)
        return

    if data_str == "prof_friends":
        await handle_friend_list(update, context)
        return

    if data_str == "draft_publish":
        draft = context.user_data.get("draft_post")
        if not draft:
            await query.edit_message_text("Черновик не найден. Попробуй создать его заново через /post_draft.")
            return
        data = load_data()
        global HEAVY_ACTIVE, HEAVY_MAX
        if HEAVY_ACTIVE >= HEAVY_MAX:
            await query.edit_message_text("Слишком много тяжёлых операций, попробуй чуть позже.")
            return
        HEAVY_ACTIVE += 1
        try:
            m = await context.bot.send_photo(
                chat_id=CHANNEL_USERNAME,
                photo=draft["photo"],
                caption=draft["caption"],
                reply_markup=draft["reply_markup"],
            )
            data["stats"]["posts_created"] += 1
            posts = data.get("posts", {})
            posts[str(m.message_id)] = {
                "title_id": draft.get("title_id"),
                "created_at": int(time.time()),
            }
            data["posts"] = posts
            save_data(data)
            context.user_data.pop("draft_post", None)
            await query.edit_message_text("Черновик опубликован в канал ✅")
        finally:
            HEAVY_ACTIVE -= 1
        return

    if data_str == "draft_cancel":
        context.user_data.pop("draft_post", None)
        await query.edit_message_text("Черновик отменён.")
        return

    if data_str.startswith("fav_add:") or data_str.startswith("fav_remove:"):
        action, title_id = data_str.split(":", 1)
        favs = user_data.get("favorites", [])
        if action == "fav_add":
            if title_id not in favs:
                favs.append(title_id)
        else:
            if title_id in favs:
                favs.remove(title_id)
        user_data["favorites"] = favs
        save_data(data)
        title = next((t for t in TITLES if t["id"] == title_id), None)
        if title:
            text = f"⭐ {title['name']}\n\n{title['desc']}"
            kb = build_title_keyboard(title_id, user_data)
            await query.edit_message_text(text, reply_markup=kb)
        else:
            await query.edit_message_text("Тайтл не найден.")
        return


POST_PHOTO, POST_CAPTION, POST_DESC, POST_WATCH = range(4)
EDIT_PHOTO, EDIT_CAPTION, EDIT_DESC, EDIT_WATCH = range(4, 8)


async def post_start_common(update: Update, context: ContextTypes.DEFAULT_TYPE, mode: str) -> int:
    data = load_data()
    if await abort_if_banned(update, data):
        return ConversationHandler.END
    user_id = update.effective_user.id
    if not is_admin(data, user_id):
        await update.effective_message.reply_text("Эта команда только для админа.")
        return ConversationHandler.END

    if check_rate_limit(user_id, "post", 3.0):
        await update.effective_message.reply_text("Слишком часто используешь эту команду, попробуй чуть позже.")
        return ConversationHandler.END

    context.user_data["post_mode"] = mode
    context.user_data.pop("post_photo", None)
    context.user_data.pop("post_caption", None)
    context.user_data.pop("post_desc_link", None)

    await update.effective_message.reply_text(
        "Шаг 1/4.\nОтправь обложку/превьюшку как фото.\n\n"
        "Если передумал — напиши /cancel."
    )
    return POST_PHOTO


async def post_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await post_start_common(update, context, mode="channel")


async def post_start_draft(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await post_start_common(update, context, mode="draft")


async def post_get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message.photo:
        await update.effective_message.reply_text("Нужно отправить именно фото. Попробуй ещё раз.")
        return POST_PHOTO

    photo = update.message.photo[-1].file_id
    context.user_data["post_photo"] = photo

    await update.effective_message.reply_text(
        "Шаг 2/4.\nТеперь отправь текст карточки, который будет под обложкой.\n\n"
        "Например:\n\n"
        "Поднятие уровня в одиночку\n\n"
        "Сезоны 1–2\n"
        "━━━▰▰▰▰▰▰▰▰\n\n"
        "4K Upscale\n"
        "..."
    )
    return POST_CAPTION


async def post_get_caption(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    context.user_data["post_caption"] = text

    await update.effective_message.reply_text(
        "Шаг 3/4.\nВставь ссылку на описание (Telegraph), как на скрине.\n"
        "Если описания пока нет — напиши просто -"
    )
    return POST_DESC


async def post_get_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    desc_link = update.message.text.strip()
    if desc_link == "-":
        desc_link = None

    context.user_data["post_desc_link"] = desc_link

    await update.effective_message.reply_text(
        "Шаг 4/4.\nТеперь отправь ссылку, где смотреть аниме "
        "(твой приватный канал/плейлист).\n"
        "Если кнопка «Смотреть» не нужна — напиши -"
    )
    return POST_WATCH


async def post_get_watch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    data = load_data()
    if await abort_if_banned(update, data):
        return ConversationHandler.END
    mode = context.user_data.get("post_mode", "channel")

    watch_link = update.message.text.strip()
    if watch_link == "-":
        watch_link = None

    photo = context.user_data.get("post_photo")
    caption = context.user_data.get("post_caption", "")
    desc_link = context.user_data.get("post_desc_link")

    keyboard = []
    if watch_link:
        keyboard.append([InlineKeyboardButton("▶ Смотреть", url=watch_link)])
    if desc_link:
        keyboard.append([InlineKeyboardButton("📖 Описание", url=desc_link)])
    markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    global HEAVY_ACTIVE, HEAVY_MAX
    if HEAVY_ACTIVE >= HEAVY_MAX:
        await update.effective_message.reply_text("Слишком много тяжёлых операций выполняется сейчас, попробуй чуть позже.")
        return ConversationHandler.END

    HEAVY_ACTIVE += 1
    try:
        if mode == "channel":
            m = await context.bot.send_photo(
                chat_id=CHANNEL_USERNAME,
                photo=photo,
                caption=caption,
                reply_markup=markup,
            )
            data["stats"]["posts_created"] += 1
            posts = data.get("posts", {})
            posts[str(m.message_id)] = {
                "title_id": None,
                "created_at": int(time.time()),
            }
            data["posts"] = posts
            save_data(data)
            await update.effective_message.reply_text("Пост отправлен в канал ✅")
        else:
            draft = {
                "photo": photo,
                "caption": caption,
                "reply_markup": markup,
                "title_id": None,
            }
            context.user_data["draft_post"] = draft
            data["stats"]["drafts_created"] += 1
            save_data(data)

            kb = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("✅ Опубликовать в канал", callback_data="draft_publish")],
                    [InlineKeyboardButton("❌ Отменить", callback_data="draft_cancel")],
                ]
            )
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=photo,
                caption=caption,
                reply_markup=kb,
            )
    finally:
        HEAVY_ACTIVE -= 1

    context.user_data.pop("post_photo", None)
    context.user_data.pop("post_caption", None)
    context.user_data.pop("post_desc_link", None)
    context.user_data.pop("post_mode", None)

    return ConversationHandler.END


async def post_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    for key in [
        "post_photo",
        "post_caption",
        "post_desc_link",
        "post_mode",
        "edit_msg_id",
        "edit_photo",
        "edit_caption",
        "edit_desc_link",
        "draft_post",
    ]:
        context.user_data.pop(key, None)
    await update.effective_message.reply_text("Операция отменена.")
    return ConversationHandler.END


def parse_message_id(arg: str) -> int | None:
    s = arg.strip()
    s = s.rstrip("/")
    if "t.me" in s:
        last_part = s.split("/")[-1]
        if "?" in last_part:
            last_part = last_part.split("?", 1)[0]
        try:
            return int(last_part)
        except ValueError:
            return None
    try:
        return int(s)
    except ValueError:
        return None


async def edit_post_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    data = load_data()
    if await abort_if_banned(update, data):
        return ConversationHandler.END
    user_id = update.effective_user.id
    if not is_admin(data, user_id):
        await update.effective_message.reply_text("Эта команда только для админа.")
        return ConversationHandler.END

    if check_rate_limit(user_id, "edit_post", 3.0):
        await update.effective_message.reply_text("Слишком часто используешь эту команду, попробуй позже.")
        return ConversationHandler.END

    if not context.args:
        await update.effective_message.reply_text(
            "Использование:\n"
            "/edit_post <ссылка на сообщение или ID>\n\n"
            "Пример:\n"
            "/edit_post https://t.me/AnimeHUB_Dream/16"
        )
        return ConversationHandler.END

    msg_id = parse_message_id(context.args[0])
    if msg_id is None:
        await update.effective_message.reply_text("Не удалось понять ID сообщения. Проверь ссылку.")
        return ConversationHandler.END

    context.user_data["edit_msg_id"] = msg_id

    await update.effective_message.reply_text(
        f"Редактирование поста с ID <code>{msg_id}</code>.\n\n"
        "Шаг 1/4.\n"
        "Отправь <b>новую обложку</b> как фото, если хочешь заменить картинку.\n"
        "Если обложку менять не нужно — напиши <code>-</code>.\n\n"
        "Если что, /cancel отменит операцию."
    )
    return EDIT_PHOTO


async def edit_post_get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.photo:
        photo = update.message.photo[-1].file_id
        context.user_data["edit_photo"] = photo
    else:
        text = (update.message.text or "").strip()
        if text == "-":
            context.user_data["edit_photo"] = None
        else:
            await update.effective_message.reply_text(
                "Отправь фото или напиши <code>-</code>, если не хочешь менять обложку."
            )
            return EDIT_PHOTO

    await update.effective_message.reply_text(
        "Шаг 2/4.\n"
        "Отправь <b>новый текст подписи</b> для поста.\n\n"
        "Можно вставить полностью ту же карточку, что и при создании."
    )
    return EDIT_CAPTION


async def edit_post_get_caption(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    caption = update.message.text or ""
    context.user_data["edit_caption"] = caption.strip()

    await update.effective_message.reply_text(
        "Шаг 3/4.\n"
        "Отправь ссылку на <b>описание (Telegraph)</b>.\n"
        "Если описания не нужно или оно остаётся пустым — напиши <code>-</code>."
    )
    return EDIT_DESC


async def edit_post_get_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    desc_link = (update.message.text or "").strip()
    if desc_link == "-":
        desc_link = None
    context.user_data["edit_desc_link"] = desc_link

    await update.effective_message.reply_text(
        "Шаг 4/4.\n"
        "Отправь ссылку, где <b>смотреть аниме</b> (кнопка «Смотреть»).\n"
        "Если кнопка «Смотреть» не нужна — напиши <code>-</code>."
    )
    return EDIT_WATCH


async def edit_post_get_watch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    data = load_data()
    if await abort_if_banned(update, data):
        return ConversationHandler.END
    watch_link = (update.message.text or "").strip()
    if watch_link == "-":
        watch_link = None

    msg_id = context.user_data.get("edit_msg_id")
    new_photo = context.user_data.get("edit_photo")
    new_caption = context.user_data.get("edit_caption", "")
    desc_link = context.user_data.get("edit_desc_link")

    keyboard = []
    if watch_link:
        keyboard.append([InlineKeyboardButton("▶ Смотреть", url=watch_link)])
    if desc_link:
        keyboard.append([InlineKeyboardButton("📖 Описание", url=desc_link)])
    markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    global HEAVY_ACTIVE, HEAVY_MAX
    if HEAVY_ACTIVE >= HEAVY_MAX:
        await update.effective_message.reply_text("Слишком много тяжёлых операций выполняется сейчас, попробуй чуть позже.")
        return ConversationHandler.END

    HEAVY_ACTIVE += 1
    try:
        try:
            if new_photo:
                media = InputMediaPhoto(media=new_photo, caption=new_caption, parse_mode=ParseMode.HTML)
                await context.bot.edit_message_media(
                    chat_id=CHANNEL_USERNAME,
                    message_id=msg_id,
                    media=media,
                    reply_markup=markup,
                )
            else:
                await context.bot.edit_message_caption(
                    chat_id=CHANNEL_USERNAME,
                    message_id=msg_id,
                    caption=new_caption,
                    reply_markup=markup,
                    parse_mode=ParseMode.HTML,
                )
        except Exception as e:
            await update.effective_message.reply_text(
                "Не удалось отредактировать пост. Возможные причины:\n"
                "• Бот не является админом в канале\n"
                "• Пост слишком старый или не создан этим ботом\n\n"
                f"Техническая ошибка: {e}"
            )
            for key in ["edit_msg_id", "edit_photo", "edit_caption", "edit_desc_link"]:
                context.user_data.pop(key, None)
            return ConversationHandler.END

        data["stats"]["posts_edited"] += 1
        save_data(data)

        for key in ["edit_msg_id", "edit_photo", "edit_caption", "edit_desc_link"]:
            context.user_data.pop(key, None)

        await update.effective_message.reply_text("Пост успешно отредактирован ✅")
        return ConversationHandler.END
    finally:
        HEAVY_ACTIVE -= 1


async def handle_link_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    if not is_admin(data, user_id):
        await update.effective_message.reply_text("Эта команда только для админа.")
        return

    if len(context.args) < 2:
        await update.effective_message.reply_text(
            "Использование:\n/link_post <ссылка или ID сообщения> <title_id>\n\n"
            "Пример:\n/link_post https://t.me/AnimeHUB_Dream/16 solo_leveling"
        )
        return

    msg_id = parse_message_id(context.args[0])
    if msg_id is None:
        await update.effective_message.reply_text("Не удалось понять ID сообщения. Проверь ссылку.")
        return

    tid = context.args[1].strip().lower()
    title = next((t for t in TITLES if t["id"] == tid), None)
    if not title:
        await update.effective_message.reply_text("❌ Тайтл с таким ID не найден.")
        return

    posts = data.get("posts", {})
    posts[str(msg_id)] = {
        "title_id": tid,
        "created_at": int(time.time()),
    }
    data["posts"] = posts
    save_data(data)

    await update.effective_message.reply_text(
        f"Пост с ID {msg_id} привязан к тайтлу «{title['name']}»."
    )


async def handle_repost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    if not is_admin(data, user_id):
        await update.effective_message.reply_text("Эта команда только для админа.")
        return

    if not context.args:
        await update.effective_message.reply_text(
            "Использование:\n/repost <ссылка или ID сообщения>\n\n"
            "Пример:\n/repost https://t.me/AnimeHUB_Dream/16"
        )
        return

    msg_id = parse_message_id(context.args[0])
    if msg_id is None:
        await update.effective_message.reply_text("Не удалось понять ID сообщения. Проверь ссылку.")
        return

    if check_rate_limit(user_id, "repost", 3.0):
        await update.effective_message.reply_text("Слишком часто используешь эту команду, попробуй чуть позже.")
        return

    global HEAVY_ACTIVE, HEAVY_MAX
    if HEAVY_ACTIVE >= HEAVY_MAX:
        await update.effective_message.reply_text("Слишком много тяжёлых операций выполняется сейчас, попробуй чуть позже.")
        return

    HEAVY_ACTIVE += 1
    try:
        try:
            m = await context.bot.copy_message(
                chat_id=CHANNEL_USERNAME,
                from_chat_id=CHANNEL_USERNAME,
                message_id=msg_id,
            )
        except Exception as e:
            await update.effective_message.reply_text(
                "Не удалось пересоздать пост. Возможные причины:\n"
                "• Бот не имеет доступа к этому сообщению\n"
                "• Сообщение не найдено\n\n"
                f"Техническая ошибка: {e}"
            )
            return

        posts = data.get("posts", {})
        old_info = posts.get(str(msg_id), {})
        posts[str(m.message_id)] = {
            "title_id": old_info.get("title_id"),
            "created_at": int(time.time()),
        }
        data["stats"]["reposts"] += 1
        data["stats"]["posts_created"] += 1
        data["posts"] = posts
        save_data(data)

        await update.effective_message.reply_text(
            f"Пост пересоздан в канале ✅\nНовый ID: <code>{m.message_id}</code>"
        )
    finally:
        HEAVY_ACTIVE -= 1


def main() -> None:
    defaults = Defaults(parse_mode=ParseMode.HTML)

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .defaults(defaults)
        .build()
    )

    conv_post = ConversationHandler(
        entry_points=[
            CommandHandler("post", post_start),
            CommandHandler("post_draft", post_start_draft),
        ],
        states={
            POST_PHOTO: [
                MessageHandler(filters.PHOTO & ~filters.COMMAND, post_get_photo)
            ],
            POST_CAPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, post_get_caption)
            ],
            POST_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, post_get_desc)
            ],
            POST_WATCH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, post_get_watch)
            ],
        },
        fallbacks=[CommandHandler("cancel", post_cancel)],
    )

    conv_edit = ConversationHandler(
        entry_points=[CommandHandler("edit_post", edit_post_start)],
        states={
            EDIT_PHOTO: [
                MessageHandler(
                    (filters.PHOTO | filters.TEXT) & ~filters.COMMAND,
                    edit_post_get_photo,
                )
            ],
            EDIT_CAPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_post_get_caption)
            ],
            EDIT_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_post_get_desc)
            ],
            EDIT_WATCH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_post_get_watch)
            ],
        },
        fallbacks=[CommandHandler("cancel", post_cancel)],
    )

    application.add_handler(conv_post)
    application.add_handler(conv_edit)

    application.add_handler(CommandHandler("start", handle_start))
    application.add_handler(CommandHandler("menu", handle_menu))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("code", handle_code))
    application.add_handler(CommandHandler("profile", handle_profile))
    application.add_handler(CommandHandler("favorites", handle_favorites))
    application.add_handler(CommandHandler("watched_add", handle_watched_add))
    application.add_handler(CommandHandler("watched_remove", handle_watched_remove))
    application.add_handler(CommandHandler("watched_list", handle_watched_list))
    application.add_handler(CommandHandler("stats", handle_stats))
    application.add_handler(CommandHandler("users", handle_users))
    application.add_handler(CommandHandler("title", handle_title))
    application.add_handler(CommandHandler("myid", handle_myid))
    application.add_handler(CommandHandler("friend_invite", handle_friend_invite))
    application.add_handler(CommandHandler("friend_requests", handle_friend_requests))
    application.add_handler(CommandHandler("friend_accept", handle_friend_accept))
    application.add_handler(CommandHandler("friend_list", handle_friend_list))
    application.add_handler(CommandHandler("friend_vs", handle_friend_vs))
    application.add_handler(CommandHandler("link_post", handle_link_post))
    application.add_handler(CommandHandler("repost", handle_repost))
    application.add_handler(CommandHandler("ban_user", handle_ban_user))
    application.add_handler(CommandHandler("unban_user", handle_unban_user))
    application.add_handler(CommandHandler("admin_list", handle_admin_list))
    application.add_handler(CommandHandler("add_admin", handle_add_admin))
    application.add_handler(CommandHandler("remove_admin", handle_remove_admin))
    application.add_handler(CallbackQueryHandler(handle_buttons))

    application.run_polling()


if __name__ == "__main__":
    main()
