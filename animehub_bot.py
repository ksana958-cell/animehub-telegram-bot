from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
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

BOT_TOKEN = "8595192008:AAFUokx5z42w-lMmlxVqrzW43tpu0U1mOGA"
CHANNEL_USERNAME = "@AnimeHUB_Dream"
DATA_FILE = "bot_data.json"

ADMINS = [813738453]

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


def load_data():
    if not os.path.exists(DATA_FILE):
        return {
            "users": {},
            "stats": {"sections": {}, "random_used": 0, "started": 0},
            "friend_requests": {},
        }
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "stats" not in data:
        data["stats"] = {"sections": {}, "random_used": 0, "started": 0}
    if "friend_requests" not in data:
        data["friend_requests"] = {}
    if "users" not in data:
        data["users"] = {}
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
    return data["users"][uid]


def inc_section_stat(data, section):
    sec = data["stats"]["sections"]
    sec[section] = sec.get(section, 0) + 1


async def is_subscribed(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
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
                await update.message.reply_text(text, reply_markup=kb)
            return

    text = SECTION_TEXTS.get(section_key, "Раздел временно недоступен.")
    kb = build_section_keyboard(section_key)
    if from_callback:
        await update.callback_query.edit_message_text(text, reply_markup=kb)
    else:
        await update.message.reply_text(text, reply_markup=kb)


async def send_random_title(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    data,
    from_callback: bool,
) -> None:
    user_id = update.effective_user.id
    user_data = get_user(data, user_id)
    data["stats"]["random_used"] += 1
    save_data(data)
    title = random.choice(TITLES)
    text = f"🎲 Случайный тайтл:\n\n⭐ {title['name']}\n\n{title['desc']}"
    kb = build_title_keyboard(title["id"], user_data)
    if from_callback:
        await update.callback_query.edit_message_text(text, reply_markup=kb)
    else:
        await update.message.reply_text(text, reply_markup=kb)


async def show_profile(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    data,
    from_callback: bool,
) -> None:
    user_id = update.effective_user.id
    user_data = get_user(data, user_id)
    fav_count = len(user_data.get("favorites", []))
    watched_150 = len(user_data.get("watched_150", []))
    friends_count = len(user_data.get("friends", []))
    access = user_data.get("access", "free")
    text = (
        "👤 Твой профиль в AnimeHUB | Dream Bot\n\n"
        f"🔑 Уровень доступа: {access}\n"
        f"⭐ Избранных тайтлов: {fav_count}\n"
        f"🏆 Прогресс по «150 лучшим аниме»: {watched_150} тайтлов\n"
        f"🤝 Друзей: {friends_count}\n\n"
        "Используй разделы бота, чтобы находить новые аниме и добавлять их в избранное."
    )
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")]]
    )
    if from_callback:
        await update.callback_query.edit_message_text(text, reply_markup=kb)
    else:
        await update.message.reply_text(text, reply_markup=kb)


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    user_id = update.effective_user.id
    user_data = get_user(data, user_id)

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
        if update.message:
            await update.message.reply_text(text, reply_markup=kb)
        else:
            await update.callback_query.edit_message_text(text, reply_markup=kb)
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
        if update.message:
            await update.message.reply_text(text, reply_markup=kb)
        else:
            await update.callback_query.edit_message_text(text, reply_markup=kb)
        return

    await show_main_menu(update, context, data)


async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    await show_main_menu(update, context, data)


async def handle_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    user_id = update.effective_user.id
    user_data = get_user(data, user_id)
    if not context.args:
        await update.message.reply_text(
            "Введите код после команды, например:\n/code AHVIP2025"
        )
        return
    code = context.args[0].strip()
    level = ACCESS_CODES.get(code)
    if not level:
        await update.message.reply_text("❌ Неверный или устаревший код доступа.")
        return
    user_data["access"] = level
    save_data(data)
    await update.message.reply_text(f"✅ Код принят. Новый уровень доступа: {level}")


async def handle_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    await show_profile(update, context, data, from_callback=False)


async def handle_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    user_id = update.effective_user.id
    if ADMINS and user_id not in ADMINS:
        await update.message.reply_text("Эта команда доступна только администратору.")
        return
    users_count = len(data["users"])
    sections = data["stats"]["sections"]
    parts = [
        f"👥 Пользователей в базе: {users_count}",
        f"🎲 Случайный тайтл использован: {data['stats']['random_used']} раз",
        "📊 Переходы по разделам:",
    ]
    for k, v in sections.items():
        parts.append(f"• {k}: {v}")
    text = "\n".join(parts)
    await update.message.reply_text(text)


async def handle_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    user_id = update.effective_user.id
    if ADMINS and user_id not in ADMINS:
        await update.message.reply_text("Эта команда доступна только администратору.")
        return

    users = data.get("users", {})
    activated_users = [uid for uid, u in users.items() if u.get("activated")]
    total = len(activated_users)

    if total == 0:
        await update.message.reply_text("Пока нет ни одного активированного пользователя.")
        return

    lines = [f"👥 Активированные пользователи: {total}"]
    for uid in activated_users:
        lines.append(f"• <a href='tg://user?id={uid}'>Пользователь {uid}</a>")

    text = "\n".join(lines)
    await update.message.reply_text(text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id in ADMINS:
        text = (
            "🛠 <b>Команды для админа</b>\n\n"
            "/start – запустить бота\n"
            "/menu – открыть главное меню навигации\n"
            "/help – показать это меню помощи\n"
            "/title &lt;id&gt; – показать карточку тайтла\n"
            "/code &lt;код&gt; – ввести код доступа\n"
            "/profile – мой профиль\n"
            "/myid – показать мой Telegram ID\n"
            "/friend_invite &lt;ID&gt; – добавить друга\n"
            "/friend_requests – входящие заявки в друзья\n"
            "/friend_accept &lt;ID&gt; – принять заявку\n"
            "/friend_list – список друзей\n"
            "/friend_vs &lt;ID&gt; – сравнить прогресс с другом\n"
            "/post – запустить мастер создания поста в канал\n"
            "/stats – статистика использования бота\n"
            "/users – список всех активированных пользователей\n\n"
            "Также можно пользоваться кнопками под сообщением: разделы, профиль, случайный тайтл."
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
            "/myid – показать мой Telegram ID\n"
            "/friend_invite &lt;ID&gt; – отправить приглашение в друзья\n"
            "/friend_requests – входящие заявки в друзья\n"
            "/friend_accept &lt;ID&gt; – принять заявку\n"
            "/friend_list – список друзей\n"
            "/friend_vs &lt;ID&gt; – сравнить прогресс по аниме с другом\n\n"
            "Основная навигация по аниме доступна через кнопки под сообщениями: тайтлы, популярное, 150 лучших, полнометражки."
        )
    await update.effective_message.reply_text(text)


async def handle_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
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
        await update.message.reply_text("❌ Тайтл с таким ID не найден.")
        return

    card = build_premium_card(title)
    await update.message.reply_text(card)


async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    query = update.callback_query
    await query.answer()
    data_str = query.data

    user_id = update.effective_user.id
    user_data = get_user(data, user_id)

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


async def post_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if ADMINS and user_id not in ADMINS:
        await update.message.reply_text("Эта команда только для админа.")
        return ConversationHandler.END

    await update.message.reply_text(
        "Шаг 1/4.\nОтправь обложку/превьюшку как фото.\n\n"
        "Если передумал — напиши /cancel."
    )
    return POST_PHOTO


async def post_get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message.photo:
        await update.message.reply_text("Нужно отправить именно фото. Попробуй ещё раз.")
        return POST_PHOTO

    photo = update.message.photo[-1].file_id
    context.user_data["post_photo"] = photo

    await update.message.reply_text(
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

    await update.message.reply_text(
        "Шаг 3/4.\nВставь ссылку на описание (Telegraph), как на скрине.\n"
        "Если описания пока нет — напиши просто -"
    )
    return POST_DESC


async def post_get_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    desc_link = update.message.text.strip()
    if desc_link == "-":
        desc_link = None

    context.user_data["post_desc_link"] = desc_link

    await update.message.reply_text(
        "Шаг 4/4.\nТеперь отправь ссылку, где смотреть аниме "
        "(твой приватный канал/плейлист).\n"
        "Если кнопка «Смотреть» не нужна — напиши -"
    )
    return POST_WATCH


async def post_get_watch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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

    await context.bot.send_photo(
        chat_id=CHANNEL_USERNAME,
        photo=photo,
        caption=caption,
        reply_markup=markup,
    )

    context.user_data.pop("post_photo", None)
    context.user_data.pop("post_caption", None)
    context.user_data.pop("post_desc_link", None)

    await update.message.reply_text("Пост отправлен в канал ✅")
    return ConversationHandler.END


async def post_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("post_photo", None)
    context.user_data.pop("post_caption", None)
    context.user_data.pop("post_desc_link", None)
    await update.message.reply_text("Создание поста отменено.")
    return ConversationHandler.END


async def handle_myid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = (
        f"Твой Telegram ID: <code>{user_id}</code>\n\n"
        "Отправь его другу, чтобы он смог добавить тебя в друзья:\n"
        "/friend_invite "
        f"{user_id}"
    )
    await update.message.reply_text(text)


async def handle_friend_invite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    from_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text(
            "Использование:\n/friend_invite <ID друга>\n\n"
            "ID друг может узнать командой /myid у себя."
        )
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return

    if target_id == from_id:
        await update.message.reply_text("Нельзя добавить в друзья самого себя.")
        return

    from_user = get_user(data, from_id)
    get_user(data, target_id)

    from_uid = str(from_id)
    target_uid = str(target_id)

    if target_uid in from_user.get("friends", []):
        await update.message.reply_text("Этот пользователь уже есть у тебя в друзьях.")
        return

    reqs = data.get("friend_requests", {})
    lst = reqs.get(target_uid, [])
    if from_uid in lst:
        await update.message.reply_text("Приглашение этому пользователю уже отправлено.")
        return

    lst.append(from_uid)
    reqs[target_uid] = lst
    data["friend_requests"] = reqs
    save_data(data)

    await update.message.reply_text(
        "✅ Приглашение в друзья отправлено.\n"
        "Скажи другу запустить бота и набрать /friend_requests, чтобы принять."
    )


async def handle_friend_requests(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    user_id = update.effective_user.id
    uid = str(user_id)
    reqs = data.get("friend_requests", {}).get(uid, [])
    if not reqs:
        await update.message.reply_text("У тебя нет входящих приглашений в друзья.")
        return

    lines = ["📨 Входящие приглашения в друзья:"]
    for rid in reqs:
        lines.append(
            f"• <a href='tg://user?id={rid}'>Пользователь {rid}</a> — принять: "
            f"/friend_accept {rid}"
        )
    text = "\n".join(lines)
    await update.message.reply_text(text)


async def handle_friend_accept(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    user_id = update.effective_user.id
    uid = str(user_id)

    if not context.args:
        await update.message.reply_text(
            "Использование:\n/friend_accept <ID>\n\n"
            "Посмотри список входящих заявок: /friend_requests"
        )
        return
    try:
        other_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return

    other_uid = str(other_id)
    reqs = data.get("friend_requests", {})
    lst = reqs.get(uid, [])

    if other_uid not in lst:
        await update.message.reply_text("От этого пользователя нет активного приглашения.")
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

    await update.message.reply_text(
        f"✅ Пользователь {other_id} добавлен в друзья.\n"
        "Теперь вы можете сравнивать прогресс по аниме: /friend_vs "
        f"{other_id}"
    )


async def handle_friend_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    user_id = update.effective_user.id
    user_data = get_user(data, user_id)
    friends = user_data.get("friends", [])
    if not friends:
        await update.message.reply_text(
            "У тебя пока нет друзей в боте.\n"
            "Отправь свой ID (/myid) другу и пусть он добавит тебя через /friend_invite."
        )
        return

    lines = ["🤝 Твой список друзей:"]
    for fid in friends:
        lines.append(f"• <a href='tg://user?id={fid}'>Пользователь {fid}</a>")
    lines.append("\nЧтобы сравнить прогресс, используй:\n/friend_vs <ID друга>")
    text = "\n".join(lines)
    await update.message.reply_text(text)


async def handle_friend_vs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text(
            "Использование:\n/friend_vs <ID друга>\n\n"
            "Сначала посмотри список друзей: /friend_list"
        )
        return
    try:
        other_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return

    uid = str(user_id)
    other_uid = str(other_id)

    user_data = get_user(data, user_id)
    other_data = get_user(data, other_id)

    if other_uid not in user_data.get("friends", []):
        await update.message.reply_text(
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
    await update.message.reply_text(text)


def main() -> None:
    defaults = Defaults(parse_mode=ParseMode.HTML)

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .defaults(defaults)
        .build()
    )

    conv_post = ConversationHandler(
        entry_points=[CommandHandler("post", post_start)],
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

    application.add_handler(conv_post)
    application.add_handler(CommandHandler("start", handle_start))
    application.add_handler(CommandHandler("menu", handle_menu))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("code", handle_code))
    application.add_handler(CommandHandler("profile", handle_profile))
    application.add_handler(CommandHandler("stats", handle_stats))
    application.add_handler(CommandHandler("users", handle_users))
    application.add_handler(CommandHandler("title", handle_title))
    application.add_handler(CommandHandler("myid", handle_myid))
    application.add_handler(CommandHandler("friend_invite", handle_friend_invite))
    application.add_handler(CommandHandler("friend_requests", handle_friend_requests))
    application.add_handler(CommandHandler("friend_accept", handle_friend_accept))
    application.add_handler(CommandHandler("friend_list", handle_friend_list))
    application.add_handler(CommandHandler("friend_vs", handle_friend_vs))
    application.add_handler(CallbackQueryHandler(handle_buttons))

    application.run_polling()


if __name__ == "__main__":
    main()
