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

# 150 лучших с постера
TOP150_POSTER = [
    "1. Стальной Алхимик",
    "2. Провожающая в последний путь Фрирен",
    "3. Легенда о героях Галактики (1988)",
    "4. Код Гиас",
    "5. Гинтама",
    "6. Крутой учитель Онидзука",
    "7. Ковбой Бибоп",
    "8. Унесённые призраками",
    "9. Хантер Х Хантер",
    "10. Твоё Имя",
    "11. Гуррен-Лаганн",
    "12. Врата Штейна",
    "13. Атака Титанов",
    "14. Тетрадь Смерти",
    "15. Город, в котором меня нет",
    "16. Ван-Пис",
    "17. Клинок, рассекающий демонов",
    "18. Для тебя Бессмертный",
    "19. Твоя апрельская ложь",
    "20. Мастер Муши",
    "21. Случайное Такси",
    "22. Волейбол!!",
    "23. Хоримия",
    "24. Монолог Фармацевта",
    "25. Сёва-Гэнроку: Двойное самоубийство по ракуго",
    "26. Реинкарнация безработного",
    "27. Форма голоса",
    "28. Берсерк (1997 года)",
    "29. Наруто",
    "30. Агент Времени",
    "31. Ходячий замок Хаула",
    "32. Моб Психо 100",
    "33. ДанДаДан",
    "34. Принцесса Мононоке",
    "35. Невероятные приключения ДжоДжо",
    "37. Обещанный Неверленд",
    "38. Моноготари / Цикл история",
    "39. Вайолет Эвергарден",
    "40. Первый шаг",
    "41. Тетрадь дружбы Нацумэ",
    "42. Сарумай Чемплу",
    "43. Сага о Винланде",
    "44. Магистр дьявольского культа",
    "45. Пинг-понг",
    "46. Брошенный кролик",
    "47. Созданный в Бездне",
    "48. Волчьи дети Амэ и Юки",
    "49. Бакуман",
    "50. Человек бензопила",
    "51. Монстр",
    "52. Блич",
    "53. Могила светлячков",
    "54. В лес, где мерцают светлячки",
    "55. Магическая битва",
    "56. Ребёнок идола",
    "57. Нодамэ Кантабиле",
    "58. Мой сосед Тоторо",
    "59. Хигару и го",
    "60. Одинокий рокер",
    "61. Радуга: Семеро из шестой камеры второго блока",
    "62. Бек",
    "63. Виви: Песнь флюоритового глаза",
    "64. Я хочу съесть твою поджелудочную",
    "65. Паразит: Учение о жизни",
    "66. Шёпот сердца",
    "67. Навсикая из Долины ветров",
    "68. Доктор Стоун",
    "69. Слэм-Данк",
    "70. Мононокэ",
    "71. Подземелье вкусностей",
    "72. Завтршний Джо",
    "73. Волчица и пряности",
    "74. Бродяга Кэнсин",
    "75. Небесный замок Лапута",
    "76. Лагерь на свежем воздухе",
    "77. Семья шпиона",
    "78. Нана",
    "79. Почувствуй Ветер",
    "80. Хеллсинг OVA",
    "81. Баракамон",
    "82. Призрак в доспех (2005) & Призрак в доспехах: Синдром одиночки",
    "83. Баскетбол Куроко",
    "84. Судьба: Начало & Судьба/Ночь схватки бесконечный мир клинков",
    "85. Дети на холме",
    "86. Ученик чудовища",
    "87. Один на вылет",
    "88. Путешествие кино (2003)",
    "89. Укрась прощальное утро цветами обещания",
    "90. Странники",
    "91. Сказ о четырёх с половиной татами",
    "92. Евангелион, нового поколения",
    "93. Триган",
    "94. РеЗеро. Жизнь с нуля в альтернативном мире",
    "95. Токийские мстители",
    "96. Ведьмина служба доставки",
    "97. Дальше, чем космос",
    "98. Летнее время",
    "99. Руки прочь от кинокружка!",
    "100. Дитя погоды",
    "101. Ванпанчмен",
    "102. Очень приятно, бог!",
    "103. Добро пожаловать в NHK",
    "104. Госпожа Кагуя: в любви как на войне",
    "105. Кайдзю номер восемь",
    "106. Этот свин не понимает мечту девочки-зайки",
    "107. Дороро",
    "108. Драгонбол (1986-1996)",
    "109. Кайдзи",
    "110. Парад смерти",
    "111. Поднятие уровня в одиночку",
    "112. Невиданный цветок",
    "113. Банановая рыба",
    "114. Ангельские ритмы",
    "115. Ветер крепчает",
    "116. Пираты \"Чёрной Лагуны\"",
    "117. Рейтинг Короля",
    "118. Бездомный бог",
    "119. Моя геройская академия",
    "120. Шумиха",
    "121. Как и ожидалось, моя школьная романтическая жизнь не удалась",
    "122. Страна самоцветов",
    "123. Эхо террора",
    "124. Девочка, покорившая время",
    "125. Дорохедоро",
    "126. Темнее чёрного",
    "127. Шаман Кигш",
    "128. Красная черта",
    "129. Однажды в Токио",
    "130. Богиня благословляет этот прекрасный мир!",
    "131. Повар-боец Сома",
    "132. Актриса тысячелетия",
    "133. Золотой парень",
    "134. Сад изящных слоёв",
    "135. Эрго Прокси",
    "136. Меч чужака",
    "137. Идеальная грусть",
    "138. Хвост Фей",
    "139. Красавица-воин Сейлор Мун (1992)",
    "140. Судзумэ, закрывающая двери",
    "141. Килл Ла Килл",
    "142. Дюрарара",
    "143. Акира",
    "144. Волчий Дождь",
    "145. Психопаспорт",
    "146. Мелакхолия Харуки Судзумии",
    "147. Мастера Меча Онлайн",
    "148. Токийский Гуль",
    "149. Эксперименты Лэйн",
    "150. Фури-Кури (2000)",
]

# 150 лучших по агрегированным рейтингам (названия в исходном виде из документа)
TOP150_RATINGS = [
    "1. Frieren: Beyond Journey's End (2023)",
    "2. Chainsaw Man the Movie: Reze Arc",
    "3. Fullmetal Alchemist: Brotherhood (2009)",
    "4. One Piece Fan Letter",
    "5. Gintama (2006)",
    "6. Clannad: After Story (2008)",
    "7. A Silent Voice",
    "8. Hunter x Hunter (1999)",
    "9. Steins;Gate (2011)",
    "10. Monster (2004)",
    "11. The Apothecary Diaries (2023)",
    "12. My Hero Academia Final Season (2025)",
    "13. Owarimonogatari Second Season",
    "14. Bleach: Thousand-Year Blood War (2022)",
    "15. Gintama. Silver Soul Arc (2018)",
    "16. Legend of the Galactic Heroes",
    "17. Your Name.",
    "18. Code Geass: Lelouch of the Rebellion (2006)",
    "19. Vinland Saga (2019)",
    "20. Takopi's Original Sin",
    "21. Mob Psycho 100 II (2019)",
    "22. Tomorrow's Joe 2 (1980)",
    "23. Spirited Away",
    "24. Monogatari Series: Second Season (2013)",
    "25. Bocchi the Rock! (2022)",
    "26. One Piece (1999)",
    "27. To Be Hero X",
    "28. Sound! Euphonium 3 (2024)",
    "29. The First Slam Dunk",
    "30. Mob Psycho 100 III (2022)",
    "31. Kaguya-sama: Love is War - Ultra Romantic (2022)",
    "32. Attack on Titan Season 3 Part 2 (2019)",
    "33. Lonesome Anime",
    "34. Bleach: Thousand-Year Blood War - The Conflict",
    "35. Mobile Suit Gundam Thunderbolt: Bandit Flower",
    "36. The Quintessential Quintuplets Movie (2022)",
    "37. Mob Psycho 100 (2016)",
    "38. Violet Evergarden (2018)",
    "39. Legend of the Galactic Heroes: Overture to a New War",
    "40. Perfect Blue",
    "41. Attack on Titan Final Season Part 2 (2022)",
    "42. Oshi no Ko (2023)",
    "43. Kizumonogatari (2016)",
    "44. March Comes In Like a Lion 2nd Season",
    "45. Attack on Titan Final Season",
    "46. Haikyuu!! Second Season",
    "47. Fruits Basket: The Final",
    "48. The Disappearance of Haruhi Suzumiya (2010)",
    "49. Ping Pong the Animation (2014)",
    "50. Odd Taxi (2021)",
    "51. Fighting Spirit (2000)",
    "52. Solo Leveling Season 2: Arise from the Shadow (2025)",
    "53. Cyberpunk: Edgerunners",
    "54. Death Note (2006)",
    "55. Kaguya-sama: Love is War (2019)",
    "56. Made in Abyss (2017)",
    "57. Bungo Stray Dogs 5 (2023)",
    "58. Haikyu!! Movie: The Dumpster Battle",
    "59. Berserk (1997)",
    "60. Kingdom: Season 2 (2013)",
    "61. Gurren Lagann The Movie: The Lights in the Sky are Stars",
    "62. March Comes In Like a Lion (2016)",
    "63. Delicious in Dungeon (2024)",
    "64. The Apothecary Diaries Season 2",
    "65. Aria the Origination",
    "66. Attack on Titan (2013)",
    "67. Golden Wind (2018)",
    "68. Rurouni Kenshin: Wandering Samurai (1996)",
    "69. Haikyuu!! Karasuno High School vs Shiratorizawa Academy",
    "70. Great Teacher Onizuka",
    "71. One Piece Film: Red",
    "72. 3-gatsu no Lion Movie",
    "73. Symphogear XV",
    "74. Kingdom: Season 3 (2020)",
    "75. Bakuman. 3rd Season",
    "76. One Piece Film: Z",
    "77. Attack on Titan: Junior High",
    "78. Haikyuu!! (2014)",
    "79. Howl's Moving Castle (2004)",
    "80. Gintama° (2015)",
    "81. Bungo Stray Dogs 4 (2023)",
    "82. Steins;Gate 0",
    "83. JoJo's Bizarre Adventure: Stone Ocean Part 3",
    "84. Code Geass: Lelouch of the Re;surrection",
    "85. Re:Zero Season 2",
    "86. Hunter x Hunter (2011)",
    "87. Made in Abyss: Dawn of the Deep Soul",
    "88. Mushishi (2005)",
    "89. One Punch Man (2015)",
    "90. Little Witch Academia (TV)",
    "91. Demon Slayer: Kimetsu no Yaiba – Entertainment District Arc",
    "92. Baccano!",
    "93. Black Lagoon",
    "94. Samurai Champloo",
    "95. Clannad",
    "96. Hellsing Ultimate",
    "97. Mononoke",
    "98. Natsume's Book of Friends",
    "99. Josee, the Tiger and the Fish",
    "100. My Neighbor Totoro",
    "101. Cowboy Bebop",
    "102. My Dress-Up Darling",
    "103. Konosuba: God's Blessing on This Wonderful World!",
    "104. March Comes in Like a Lion Movie 2",
    "105. 5 Centimeters Per Second",
    "106. Garden of Words",
    "107. A Place Further Than the Universe",
    "108. Planetes",
    "109. Violet Evergarden: Eternity and the Auto Memory Doll",
    "110. I Want to Eat Your Pancreas",
    "111. Banana Fish",
    "112. Angel Beats!",
    "113. Ranking of Kings",
    "114. Noragami Aragoto",
    "115. The Wind Rises",
    "116. My Teen Romantic Comedy SNAFU Climax!",
    "117. Land of the Lustrous",
    "118. Kaiji: Ultimate Survivor",
    "119. Barakamon",
    "120. Welcome to the N.H.K.",
    "121. Grand Blue",
    "122. KonoSuba: Legend of Crimson",
    "123. Jujutsu Kaisen",
    "124. Tokyo Revengers",
    "125. Toradora!",
    "126. Dororo",
    "127. Psycho-Pass",
    "128. Elfen Lied",
    "129. Tokyo Ghoul",
    "130. Fairy Tail",
    "131. Erased",
    "132. Your Lie in April",
    "133. Soul Eater",
    "134. Mob Psycho 100 Reigen",
    "135. Kill la Kill",
    "136. Durarara!!",
    "137. AKIRA",
    "138. Wolf's Rain",
    "139. Melancholy of Haruhi Suzumiya",
    "140. Angel's Egg",
    "141. Ergo Proxy",
    "142. The Tatami Galaxy",
    "143. Paranoia Agent",
    "144. FLCL (2000)",
    "145. Suzume",
    "146. Weathering with You",
    "147. Blue Giant",
    "148. Medalist",
    "149. Ping Pong (OVA)",
    "150. Haikyuu!! To the Top (2020)",
]

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


def split_lines_for_telegram(lines: list[str], header: str, max_chars: int = 3800) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_len = len(header) + 2

    for line in lines:
        line_len = len(line) + 1
        if current and current_len + line_len > max_chars:
            chunks.append(header + "\n\n" + "\n".join(current))
            current = [line]
            current_len = len(header) + 2 + line_len
        else:
            current.append(line)
            current_len += line_len

    if current:
        chunks.append(header + "\n\n" + "\n".join(current))

    return chunks


async def show_top150_poster(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    header = "📜 150 лучших аниме по постеру"
    text = header + "\n\n" + "\n".join(TOP150_POSTER)
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⬅️ Назад к выбору списка", callback_data="sec_top150")],
            [InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")],
        ]
    )
    await query.edit_message_text(text, reply_markup=kb)


async def show_top150_ratings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    header = (
        "🌐 150 лучших аниме по рейтингам\n\n"
        "Список сформирован на основе оценок пользователей:\n"
        "• MyAnimeList\n"
        "• Shikimori\n"
        "• Кинопоиск\n"
        "• IMDb\n\n"
        "Названия приведены так, как в источниках (оригинальные / англ.)."
    )
    parts = split_lines_for_telegram(TOP150_RATINGS, header)

    kb_first = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⬅️ Назад к выбору списка", callback_data="sec_top150")],
            [InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")],
        ]
    )

    await query.edit_message_text(parts[0], reply_markup=kb_first)

    for i in range(1, len(parts)):
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=parts[i],
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
    if required_access and not has_access(user_data, required_access):
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

    if section_key == "top150":
        text = (
            "🏆 Раздел «150 лучших аниме»\n\n"
            "Выбери, какой список открыть:\n\n"
            "📜 <b>150 по постеру</b> — тот самый постер на стене.\n"
            "🌐 <b>150 по рейтингам</b> — агрегированный топ на основе MyAnimeList, "
            "Shikimori, Кинопоиска и IMDb.\n"
        )
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("📜 150 по постеру", callback_data="top150_poster")],
                [InlineKeyboardButton("🌐 150 по рейтингам", callback_data="top150_ratings")],
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
    if ADMINS and user_id not in ADMINS:
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
    if ADMINS and user_id not in ADMINS:
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
        lines.append(f"• <a href='tg://user?id={uid}'>{name}</a> — ID: <code>{uid}</code>")
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
    if user_id in ADMINS:
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
            "/unban_user &lt;ID&gt; – разблокировать пользователя\n\n"
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
            "/friend_requests – входящие приглашения в друзья\n"
            "/friend_accept &lt;ID&gt; – принять приглашение\n"
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

    if not context.args:
        await update.effective_message.reply_text(
            "Использование:\n"
            "/friend_invite <ID друга или @username>\n\n"
            "ID друг может узнать командой /myid у себя."
        )
        return

    arg = context.args[0].strip()

    target_id = None
    if arg.startswith("@"):
        username = arg[1:].lower()
        for uid, u in data.get("users", {}).items():
            if (u.get("username") or "").lower() == username:
                target_id = int(uid)
                break
        if target_id is None:
            await update.effective_message.reply_text(
                "Пользователь с таким @username не найден среди активированных.\n"
                "Попроси его сначала запустить бота и активировать профиль."
            )
            return
    else:
        try:
            target_id = int(arg)
        except ValueError:
            await update.effective_message.reply_text("ID должен быть числом или @username.")
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
        lines.append(f"• <a href='tg://user?id={fid}'>{name}</a> — ID: <code>{fid}</code>")
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
    if ADMINS and user_id not in ADMINS:
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
    if ADMINS and user_id not in ADMINS:
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

    if data_str == "top150_poster":
        await show_top150_poster(update, context)
        return

    if data_str == "top150_ratings":
        await show_top150_ratings(update, context)
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
    if ADMINS and user_id not in ADMINS:
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
    if ADMINS and user_id not in ADMINS:
        await update.effective_message.reply_text("Эта команда только для админа.")
        return ConversationHandler.END

    if check_rate_limit(user_id, "edit_post", 3.0):
        await update.effective_message.reply_text("Слишком часто используешь эту команду, попробуй чуть позже.")
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
    if ADMINS and user_id not in ADMINS:
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
    if ADMINS and user_id not in ADMINS:
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
    application.add_handler(CallbackQueryHandler(handle_buttons))

    application.run_polling()


if __name__ == "__main__":
    main()
