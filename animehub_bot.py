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
)
import json
import os
import random
import time

# 🔧 НАСТРОЙКИ — ЗАПОЛНИ СВОИ ДАННЫЕ
BOT_TOKEN = "8259407812:AAHkRjdYPoO8wMt-yjoxdLGJhfV-wgFYp34"
CHANNEL_USERNAME = "@AnimeHUB_Dream"  # юзернейм канала с @
DATA_FILE = "bot_data.json"
ADMINS = []  # сюда можно добавить свой Telegram ID: [123456789]


# 📚 БАЗОВЫЙ СПИСОК ТАЙТЛОВ (можно дополнять)
TITLES = [
 {
    "id": "solo_leveling",
    "name": "Поднятие уровня в одиночку",
    "season": "Сезоны 1–2",
    "status": "Вышел",
    "episodes": "25",
    "year": "2024–2025",
    "studio": "A-1 Pictures",
    "author": "Chugong",
    "director": "Ясунори Одзаки",
    "voice": "AniDub / Crunchyroll",
    "shiki": "8.45",
    "imdb": "8.2",
    "kp": "8.0",
    "genres": "#Экшен #Фэнтези #Система #Охотники #Демоны",
    "playlist": "Сезоны 1–2",
    "watch_url": "https://t.me/+cKLGtPy54BY4NzA6",  # ← вот это главное
    "desc": (
        "Самый слабый охотник Сон Джин-Ву получает уникальную систему прокачки, "
        "которая позволяет ему становиться сильнее без ограничений. "
        "Шаг за шагом он превращается из слабейшего ранга E в самого опасного "
        "и непостижимого охотника современности."
    ),
},

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
    "hot_past": (
        "⭐ Раздел «Популярно в другие года»\n\n"
        "Тайтлы, которые были хайпом раньше, но всё ещё достойны просмотра.\n"
        "Классика, хиты прошлых сезонов и просто проверенные временем аниме.\n\n"
        "Ищи соответствующие подборки и плейлисты в канале."
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
        return {"users": {}, "stats": {"sections": {}, "random_used": 0, "started": 0}}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


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
            "created_at": int(time.time()),
        }
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
        [InlineKeyboardButton("⭐ Популярно в другие года", callback_data="sec_hot_past")],
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
    if section in ("titles", "hot_now", "hot_past", "top150", "movies"):
        row.append(
            InlineKeyboardButton(
                "🏠 Открыть канал",
                url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}",
            )
        )
    keyboard = [row]
    return InlineKeyboardMarkup(keyboard)


def build_title_keyboard(title_id: str, user_data: dict) -> InlineKeyboardMarkup:
    title = next((t for t in TITLES if t["id"] == title_id), None)

    favs = user_data.get("favorites", [])
    if title_id in favs:
        fav_text = "⭐ Убрать из избранного"
        fav_cb = f"fav_remove:{title_id}"
    else:
        fav_text = "⭐ В избранное"
        fav_cb = f"fav_add:{title_id}"

    keyboard = []

        # ▶️ Смотреть — только если есть watch_url
    if title and "watch_url" in title:
        keyboard.append([
            InlineKeyboardButton(
                "▶️ Смотреть",
                url=title["watch_url"]
            )
        ])

    title = next((t for t in TITLES if t["id"] == title_id), None)

    buttons = []

    # ▶ Смотреть (если есть URL)
    if title and title.get("watch_url"):
        buttons.append([
            InlineKeyboardButton("▶ Смотреть", url=title["watch_url"])
        ])

    # ⭐ Избранное
    if is_fav:
        buttons.append([
            InlineKeyboardButton("⭐ Убрать из избранного", callback_data=f"fav_remove:{title_id}")
        ])
    else:
        buttons.append([
            InlineKeyboardButton("⭐ В избранное", callback_data=f"fav_add:{title_id}")
        ])

    # ⬅️ Главное меню
    buttons.append([
        InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")
    ])

    return InlineKeyboardMarkup(buttons)

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
        "• ⭐ «Популярно в другие года»\n"
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
    access = user_data.get("access", "free")
    text = (
        "👤 Твой профиль в AnimeHUB | Dream Bot\n\n"
        f"🔑 Уровень доступа: {access}\n"
        f"⭐ Избранных тайтлов: {fav_count}\n"
        f"🏆 Прогресс по «150 лучшим аниме»: {watched_150} тайтлов\n\n"
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
    args = context.args
    section = args[0].strip().lower() if args else None
    if section in SECTION_TEXTS:
        await send_section(update, context, data, section, from_callback=False)
    else:
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
        f"👥 Пользователей: {users_count}",
        f"🎲 Случайный тайтл использован: {data['stats']['random_used']} раз",
        "📊 Переходы по разделам:",
    ]
    for k, v in sections.items():
        parts.append(f"• {k}: {v}")
    text = "\n".join(parts)
    await update.message.reply_text(text)

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
        user_id = update.effective_user.id
        user_data = get_user(data, user_id)
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

def main() -> None:
    # Значение по умолчанию: все сообщения в HTML-разметке
    defaults = Defaults(parse_mode=ParseMode.HTML)

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .defaults(defaults)   # привязываем defaults к приложению
        .build()
    )

    application.add_handler(CommandHandler("start", handle_start))
    application.add_handler(CommandHandler("menu", handle_menu))
    application.add_handler(CommandHandler("code", handle_code))
    application.add_handler(CommandHandler("profile", handle_profile))
    application.add_handler(CommandHandler("stats", handle_stats))
    application.add_handler(CommandHandler("title", handle_title))
    application.add_handler(CallbackQueryHandler(handle_buttons))

    application.run_polling()

if __name__ == "__main__":
    main()