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
    "movies": "free",
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
        "hot": True,
        "added_at": int(time.time()),
    },
]

SECTION_TEXTS = {
    "titles": (
        "📚 <b>Раздел «Аниме по тайтлам»</b>\n\n"
        "Здесь будет удобный список всех тайтлов, доступных в AnimeHUB | Dream.\n"
        "Пока что ты можешь:\n"
        "• открыть канал и найти нужный тайтл по поиску\n"
        "• или воспользоваться командой: <code>/search название</code>\n\n"
        "Если хочешь — я сделаю лист по буквам (А–Я) + кнопки пагинации."
    ),
    "hot_now": (
        "🔥 <b>Раздел «Популярно сейчас»</b>\n\n"
        "Здесь появляются тайтлы, которые сейчас в фокусе: новинки, топовые релизы,\n"
        "то, что чаще всего открывают и добавляют в избранное на AnimeHUB | Dream.\n"
    ),
    "top150": (
        "🏆 <b>Раздел «150 лучших аниме»</b>\n\n"
        "Раздел основан на постере «150 лучших аниме».\n"
        "Постепенно все тайтлы с постера будут появляться в канале в высоком качестве.\n\n"
        "Используй канал как онлайн-версию постера и отмечай для себя уже просмотренное."
    ),
    "movies": (
        "🎬 <b>Раздел «Полнометражки»</b>\n\n"
        "Здесь будет отдельный список аниме-фильмов: полнометражные продолжения, спин-оффы,\n"
        "самостоятельные истории и классика формата movie.\n\n"
        "Если хочешь — сделаю:\n"
        "• список фильмов кнопками\n"
        "• или быстрый поиск: <code>/search movie</code>\n"
    ),
}

TOP150_POSTER_LIST = [
    "Стальной Алхимик",
    "Провожающая в последний путь Фрирен",
    "Легенда о героях Галактики (1988)",
    "Код Гиас",
    "Гинтама",
    "Крутой учитель Онидзука",
    "Ковбой Бибоп",
    "Унесённые призраками",
    "Хантер Х Хантер",
    "Твоё Имя",
    "Гуррен-Лаганн",
    "Врата Штейна",
    "Атака Титанов",
    "Тетрадь Смерти",
    "Город, в котором меня нет",
    "Ван-Пис",
    "Клинок, рассекающий демонов",
    "Для тебя Бессмертный",
    "Твоя апрельская ложь",
    "Мастер Муши",
    "Случайное Такси",
    "Волейбол!!",
    "Хоримия",
    "Монолог Фармацевта",
    "Сёва-Гэнроку: Двойное самоубийство по ракуго",
    "Реинкарнация безработного",
    "Форма голоса",
    "Берсерк (1997 года)",
    "Наруто",
    "Агент Времени",
    "Ходячий замок Хаула",
    "Моб Психо 100",
    "ДанДаДан",
    "Принцесса Мононоке",
    "Невероятные приключения ДжоДжо",
    "Плутон",
    "Обещанный Неверленд",
    "Моноготари / Цикл история",
    "Вайолет Эвергарден",
    "Первый шаг",
    "Тетрадь дружбы Нацумэ",
    "Самурай Чемплу",
    "Сага о Винланде",
    "Магистр дьявольского культа",
    "Пинг-понг",
    "Брошенный кролик",
    "Созданный в Бездне",
    "Волчьи дети Амэ и Юки",
    "Бакуман",
    "Человек бензопила",
    "Монстр",
    "Блич",
    "Могила светлячков",
    "В лес, где мерцают светлячки",
    "Магическая битва",
    "Ребёнок идола",
    "Нодамэ Кантабиле",
    "Мой сосед Тоторо",
    "Хикару и го",
    "Одинокий рокер",
    "Радуга: Семеро из шестой камеры второго блока",
    "Бек",
    "Виви: Песнь флюоритового глаза",
    "Я хочу съесть твою поджелудочную",
    "Паразит: Учение о жизни",
    "Шёпот сердца",
    "Навсикая из Долины ветров",
    "Доктор Стоун",
    "Слэм-Данк",
    "Мононокэ",
    "Подземелье вкусностей",
    "Завтрашний Джо",
    "Волчица и пряности",
    "Бродяга Кэнсин",
    "Небесный замок Лапута",
    "Лагерь на свежем воздухе",
    "Семья шпиона",
    "Нана",
    "Почувствуй ветер",
    "Хеллсинг OVA",
    "Баракамон",
    "Призрак в доспех (2005) & Призрак в доспехах: Синдром одиночки",
    "Баскетбол Куроко",
    "Судьба: Начало & Судьба/Ночь схватки бесконечный мир клинков",
    "Дети на холме",
    "Ученик чудовища",
    "Один на вылет",
    "Путешествие кино (2003)",
    "Укрась прощальное утро цветами обещания",
    "Странники",
    "Сказ о четырёх с половиной татами",
    "Евангелион, нового поколения",
    "Триган",
    "РеЗеро. Жизнь с нуля в альтернативном мире",
    "Токийские мстители",
    "Ведьмина служба доставки",
    "Дальше, чем космос",
    "Летнее время",
    "Руки прочь от кинокружка!",
    "Дитя погоды",
    "Ванпанчмен",
    "Очень приятно, бог!",
    "Добро пожаловать в NHK",
    "Госпожа Кагуя: в любви как на войне",
    "Кайдзю номер восемь",
    "Этот свин не понимает мечту девочки-зайки",
    "Дороро",
    "Драгонбол (1986-1996)",
    "Кайдзи",
    "Парад смерти",
    "Поднятие уровня в одиночку",
    "Невиданный цветок",
    "Банановая рыба",
    "Ангельские ритмы",
    "Ветер крепчает",
    "Пираты \"Чёрной Лагуны\"",
    "Рейтинг Короля",
    "Бездомный бог",
    "Моя геройская академия",
    "Шумиха",
    "Как и ожидалось, моя школьная романтическая жизнь не удалась",
    "Страна самоцветов",
    "Эхо террора",
    "Девочка, покорившая время",
    "Дорохедоро",
    "Темнее чёрного",
    "Шаман Кинг",
    "Красная черта",
    "Однажды в Токио",
    "Богиня благословляет этот прекрасный мир!",
    "Повар-боец Сома",
    "Актриса тысячелетия",
    "Сад изящных слоёв",
    "Эрго Прокси",
    "Меч чужака",
    "Идеальная грусть",
    "Хвост Фей",
    "Красавица-воин Сейлор Мун (1992)",
    "Судзумэ, закрывающая двери",
    "Килл Ла Килл",
    "Дюрарара",
    "Акира",
    "Волчий Дождь",
    "Психопаспорт",
    "Меланхолия Харуки Судзумии",
    "Мастера Меча Онлайн",
    "Токийский Гуль",
    "Эксперименты Лэйн",
    "Фури-Кури (2000)",
]

TOP150_MERGED_LIST = [
    "Fullmetal Alchemist: Brotherhood — Стальной алхимик: Братство",
    "Steins;Gate — Врата Штейна",
    "Frieren: Beyond Journey's End — Провожающая в последний путь Фрирен",
    "Attack on Titan — Атака титанов",
    "Hunter x Hunter — Охотник × Охотник",
    "Code Geass — Код Гиас",
    "Gintama — Гинтама",
    "One Piece — Ван-Пис",
    "Tengen Toppa Gurren Lagann — Гуррен-Лаганн",
    "Vinland Saga — Сага о Винланде",
    "Bleach — Блич",
    "Death Note — Тетрадь смерти",
    "Monster — Монстр",
    "Neon Genesis Evangelion — Евангелион нового поколения",
    "Clannad — Кланнад",
    "Kenpuu Denki Berserk — Берсерк (1997)",
    "Re:Zero − Starting Life in Another World — Re:Zero. Жизнь с нуля в альтернативном мире",
    "Monogatari Series — Цикл историй (Monogatari)",
    "Noragami — Бездомный бог",
    "Sen to Chihiro no Kamikakushi — Унесённые призраками",
    "Made in Abyss — Созданный в Бездне",
    "Death Note — Тетрадь смерти",
    "The Tatami Galaxy — Сказ о четырёх с половиной татами",
    "Naruto — Наруто",
    "Banana Fish — Банановая рыба",
    "Violet Evergarden — Вайолет Эвергарден",
    "Barakamon — Баракамон",
    "Odd Taxi — Случайное такси",
    "Monster — Монстр",
    "Bocchi the Rock! — Одинокий рокер!",
    "A Place Further Than the Universe — Дальше, чем космос",
    "A Silent Voice (Koe no Katachi) — Форма голоса",
    "Your Name (Kimi no Na wa) — Твоё имя",
    "Wolf Children — Волчьи дети Амэ и Юки",
    "Kaguya-sama: Love Is War — Госпожа Кагуя: в любви как на войне",
    "Princess Mononoke — Принцесса Мононоке",
    "Howl no Ugoku Shiro — Ходячий замок",
    "My Neighbor Totoro — Мой сосед Тоторо",
    "Grave of the Fireflies — Могила светлячков",
    "The Girl Who Leapt Through Time — Девочка, покорившая время",
    "Mushoku Tensei: Isekai Ittara Honki Dasu — Реинкарнация безработного",
    "Demon Slayer: Kimetsu no Yaiba — Клинок, рассекающий демонов",
    "Jujutsu Kaisen — Магическая битва",
    "Chainsaw Man — Человек-бензопила",
    "My Hero Academia — Моя геройская академия",
    "Dr. Stone — Доктор Стоун",
    "Haikyu!! — Волейбол!!",
    "Kuroko’s Basketball — Баскетбол Куроко",
    "Slam Dunk — Слэм-данк",
    "Hajime no Ippo — Первый шаг",
    "One-Punch Man — Ванпанчмен",
    "Konosuba: God’s Blessing on This Wonderful World! — Богиня благословляет этот прекрасный мир!",
    "No Game No Life — Нет игры — нет жизни",
    "Hellsing Ultimate — Хеллсинг OVA",
    "Black Lagoon — Пираты «Чёрной Лагуны»",
    "Samurai Champloo — Самурай Чамплу",
    "Cowboy Bebop — Ковбой Бибоп",
    "Great Teacher Onizuka — Крутой учитель Онидзука",
    "Toradora! — ТораДора!",
    "Spice and Wolf — Волчица и пряности",
    "Horimiya — Хоримия",
    "Fruits Basket (2019) — Фруктовая корзина (2019)",
    "Your Lie in April — Твоя апрельская ложь",
    "Angel Beats! — Ангельские ритмы",
    "Nana — Нана",
    "Anohana: The Flower We Saw That Day — Невиданный цветок",
    "Welcome to the N.H.K. — Добро пожаловать в NHK",
    "Hyouka — Хёка",
    "Oregairu (My Teen Romantic Comedy SNAFU) — Как и ожидалось, моя школьная романтическая жизнь не удалась",
    "Laid-Back Camp (Yuru Camp) — Лагерь на свежем воздухе",
    "Oshi no Ko — Ребёнок идола",
    "Cyberpunk: Edgerunners — Киберпанк: Бегущие по краю",
    "86 Eighty-Six — Восемьдесят шесть",
    "Parasyte: The Maxim — Паразит: Учение о жизни",
    "The Promised Neverland (season 1) — Обещанный Неверленд",
    "Erased (Boku dake ga Inai Machi) — Город, в котором меня нет",
    "Terror in Resonance — Эхо террора",
    "Durarara!! — Дюрарара!!",
    "Darker than Black — Темнее чёрного",
    "Elfen Lied — Эльфийская песнь",
    "Future Diary — Дневник будущего",
    "Another — Иная",
    "Guilty Crown — Корона вины",
    "Pandora Hearts — Сердца Пандоры",
    "Ashita no Joe — Завтрашний Джо",
    "Sword Art Online — Мастера меча онлайн",
    "Fairy Tail — Хвост феи",
    "Psycho-Pass — Психопаспорт",
    "Dungeon Meshi — Подземелье вкусностей",
    "Blue Exorcist — Синий экзорцист",
    "Fate/Zero — Fate/Zero",
    "Fate/stay night: Unlimited Blade Works — Судьба: Ночь схватки — Клинков бесконечный край",
    "Puella Magi Madoka Magica — Девочка-волшебница Мадока Магика",
    "Natsume’s Book of Friends — Тетрадь дружбы Нацумэ",
    "ReLIFE — ReLIFE",
    "Beck — Бек",
    "Bakuman — Бакуман",
    "Golden Boy — Золотой парень",
    "School Rumble — Школьные войны",
    "Daily Lives of High School Boys — Повседневная жизнь старшеклассников",
    "Nichijou — Повседневная жизнь",
    "Saiki Kusuo no Ψ-nan — Разрушительная жизнь Саики Кусо",
    "K-ON! — Кэйон!",
    "Free! — Вольный стиль!",
    "Dragon Ball — Драконий жемчуг",
    "Planetes — Странники",
    "Space Brothers — Космические братья",
    "Mob Psycho 100 — Моб Психо 100",
    "Kill la Kill — Килл ла Килл",
    "FLCL (Fooly Cooly) — Фури-Кури",
    "Serial Experiments Lain — Эксперименты Лэйн",
    "Perfect Blue — Идеальная грусть",
    "Bakuman. — Бакуман",
    "Akira — Акира",
    "Ergo Proxy — Эрго Прокси",
    "Texhnolyze — Технолайз",
    "Black Butler — Тёмный дворецкий",
    "D.Gray-man — Ди.Грей-мен",
    "Magi: The Labyrinth of Magic — Маги: Лабиринт волшебства",
    "Enen no Shouboutai — Пламенная бригада пожарных",
    "Baccano! — Шумиха!",
    "Sword Art Online — Мастера Меча Онлайн",
    "Dororo — Дороро",
    "Drifters — Скитальцы",
    "Goblin Slayer — Убийца гоблинов",
    "Tokyo Ghoul — Токийский гуль",
    "Tokyo Revengers — Токийские мстители",
    "Devilman: Crybaby — Девилмэн: Плакса",
    "Hellsing (TV) — Хеллсинг",
    "Shaman King — Шаман Кинг",
    "Soul Eater — Пожиратель душ",
    "Inuyasha — Инуяша",
    "Kingdom — Царство",
    "Kenshin (TV) — Бродяга Кэнсин",
    "Trigun — Триган",
    "JoJo’s Bizarre Adventure — Невероятные приключения ДжоДжо",
    "Barakamon — Баракамон",
    "Nanatsu no Taizai — Семь смертных грехов",
    "Land of the Lustrous — Страна самоцветов",
    "Higurashi: When They Cry — Когда плачут цикады",
    "Boku dake ga Inai Machi — Город, в котором меня нет",
    "Black Clover — Чёрный клевер",
    "Grappler Baki (TV) — Боец Баки",
    "Josee, the Tiger and the Fish — Дзёсэ, тигр и рыба",
    "Tenki no Ko — Дитя погоды",
    "Children Who Chase Lost Voices — Дети, ищущие потерянные голоса",
    "The Wind Rises — Ветер крепчает",
    "5 Centimeters per Second — 5 сантиметров в секунду",
    "Angel’s Egg — Яйцо ангела",
    "Spy x Family — Семья шпиона",
]

TOP150_PAGE_SIZE = 25

def build_top150_page_text(kind: str, page: int) -> tuple[str, int, int]:
    data_list = TOP150_POSTER_LIST if kind == "poster" else TOP150_MERGED_LIST
    total = len(data_list)
    total_pages = (total + TOP150_PAGE_SIZE - 1) // TOP150_PAGE_SIZE
    if total_pages == 0:
        return "Список пуст.", 1, 1
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages
    start = (page - 1) * TOP150_PAGE_SIZE
    end = min(start + TOP150_PAGE_SIZE, total)
    if kind == "poster":
        header = "🏆 150 лучших аниме — список постера\n"
    else:
        header = "🏆 150 лучших аниме — объединённый рейтинг\n"
    lines = [
        header,
        f"Страница {page}/{total_pages}\n",
    ]
    for i in range(start, end):
        pos = i + 1
        title = data_list[i]
        lines.append(f"{pos}. {title}")
    text = "\n".join(lines)
    return text, page, total_pages

def build_top150_page_keyboard(kind: str, page: int, total_pages: int) -> InlineKeyboardMarkup:
    keyboard = []
    prefix = "top150_poster_page" if kind == "poster" else "top150_merged_page"
    if page > 1 or page < total_pages:
        row = []
        if page > 1:
            row.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"{prefix}_{page - 1}"))
        if page < total_pages:
            row.append(InlineKeyboardButton("Вперёд ➡️", callback_data=f"{prefix}_{page + 1}"))
        if row:
            keyboard.append(row)
    other_kind = "merged" if kind == "poster" else "poster"
    other_text = "⭐ Объединённый рейтинг" if kind == "poster" else "📜 Список постера"
    other_prefix = "top150_merged_page" if other_kind == "merged" else "top150_poster_page"
    keyboard.append([InlineKeyboardButton(other_text, callback_data=f"{other_prefix}_1")])
    keyboard.append(
        [
            InlineKeyboardButton("⬅️ К выбору списка", callback_data="sec_top150"),
            InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu"),
        ]
    )
    return InlineKeyboardMarkup(keyboard)

ACCESS_CODES = {
    "AHVIP2025": "vip",
    "AHFRIENDS": "friend",
}

LAST_BOT_MESSAGE_KEY = "last_bot_message_id"

async def send_with_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, **kwargs):
    chat_id = update.effective_chat.id
    user_store = context.user_data
    last_id = user_store.get(LAST_BOT_MESSAGE_KEY)
    if last_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=last_id)
        except Exception:
            pass
    sent = await update.effective_message.reply_text(text, **kwargs)
    user_store[LAST_BOT_MESSAGE_KEY] = sent.message_id
    return sent

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
        "invites": {},
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
    if "invites" not in data:
        data["invites"] = {}

    posts = data.get("posts", {})
    for mid, info in posts.items():
        if "caption" not in info:
            info["caption"] = None
    data["posts"] = posts
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
            "weekly_150_start": 0,
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
        if "weekly_150_start" not in u:
            u["weekly_150_start"] = len(u.get("watched_150", []))
    return data["users"][uid]

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
        [InlineKeyboardButton("📩 Предложить тайтл", callback_data="suggest_info")],
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
    return InlineKeyboardMarkup([row])

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

def wrap_text_by_words(text: str, limit: int = 40) -> str:
    words = text.split()
    if not words:
        return text
    lines = []
    current = words[0]
    for w in words[1:]:
        if len(current) + 1 + len(w) > limit:
            lines.append(current)
            current = w
        else:
            current += " " + w
    lines.append(current)
    return "\n".join(lines)

def format_genres(genres: str, max_tags: int = 3, line_limit: int = 40) -> str:
    parts = genres.split()
    if not parts:
        return "-"
    if max_tags and len(parts) > max_tags:
        parts = parts[:max_tags]
    short = " ".join(parts)
    return wrap_text_by_words(short, line_limit)

def build_premium_card(title: dict) -> str:
    access = title.get("min_access", "free")
    access_label = {
        "free": "Открыт для всех",
        "friend": "Доступ для друзей",
        "vip": "VIP-доступ",
    }.get(access, "Ограниченный доступ")

    genres_raw = title.get("genres", "-")
    if genres_raw and genres_raw != "-":
        genres_text = format_genres(genres_raw, max_tags=3, line_limit=40)
    else:
        genres_text = "-"

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
        f"{genres_text}\n\n"
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
        await send_with_cleanup(update, context, text, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

async def render_hot_now(data, user_data):
    hot_titles = [t for t in TITLES if t.get("hot")]
    hot_titles.sort(key=lambda t: t.get("added_at", 0), reverse=True)
    if not hot_titles:
        return SECTION_TEXTS["hot_now"] + "\n\nСписок тайтлов скоро появится."

    lines = [SECTION_TEXTS["hot_now"].rstrip(), ""]
    lines.append("🔥 <b>Сейчас в фокусе:</b>")
    for t in hot_titles[:25]:
        lines.append(f"• <b>{t['name']}</b> — <code>/title {t['id']}</code>")
    return "\n".join(lines)

async def send_section(update: Update, context: ContextTypes.DEFAULT_TYPE, data, section_key: str, from_callback: bool) -> None:
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
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")]])
        if from_callback:
            await update.callback_query.edit_message_text(text, reply_markup=kb)
        else:
            await update.effective_message.reply_text(text, reply_markup=kb)
        save_data(data)
        return

    inc_section_stat(data, section_key)
    save_data(data)

    if section_key == "top150":
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

        text = (
            SECTION_TEXTS["top150"]
            + "\n\n"
            "Выбери формат списка:\n\n"
            "📜 Список постера — ранги с 1 по 150 как на постере.\n"
            "⭐ Объединённый рейтинг — сводный список по рейтингу сайтов.\n"
        )
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("📜 Список постера", callback_data="top150_poster_page_1")],
                [InlineKeyboardButton("⭐ Объединённый рейтинг", callback_data="top150_merged_page_1")],
                [InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")],
            ]
        )
        if from_callback:
            await update.callback_query.edit_message_text(text, reply_markup=kb)
        else:
            await update.effective_message.reply_text(text, reply_markup=kb)
        return

    if section_key == "hot_now":
        text = await render_hot_now(data, user_data)
    else:
        text = SECTION_TEXTS.get(section_key, "Раздел скоро появится.")

    kb = build_section_keyboard(section_key)
    if from_callback:
        await update.callback_query.edit_message_text(text, reply_markup=kb)
    else:
        await update.effective_message.reply_text(text, reply_markup=kb)

async def send_random_title(update: Update, context: ContextTypes.DEFAULT_TYPE, data, from_callback: bool) -> None:
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
        await send_with_cleanup(update, context, text, reply_markup=kb)

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, data, from_callback: bool) -> None:
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

def ensure_friend_access(user_data):
    current = user_data.get("access", "free")
    if ACCESS_LEVELS.get("friend", 1) > ACCESS_LEVELS.get(current, 0):
        user_data["access"] = "friend"

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

    if args:
        arg0 = args[0].strip()
        if arg0.lower() == "activate":
            user_data["activated"] = True
            save_data(data)
            text = (
                "⚡ Профиль активирован!\n\n"
                f"Твой Telegram ID: <code>{user_id}</code>\n\n"
                "Теперь ты можешь:\n"
                "• Добавлять друзей через /friend_invite\n"
                "• Смотреть входящие заявки: /friend_requests\n"
                "• Список друзей: /friend_list\n\n"
                "Нажми кнопку ниже, чтобы открыть главное меню."
            )
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("📚 Открыть главное меню", callback_data="main_menu")]])
            await update.effective_message.reply_text(text, reply_markup=kb)
            return

        if arg0.startswith("friend_"):
            token = arg0
            invites = data.get("invites", {})
            info = invites.get(token)
            if info and info.get("type") == "friend":
                ensure_friend_access(user_data)
                user_data["activated"] = True
                info["uses"] = info.get("uses", 0) + 1
                max_uses = info.get("max_uses")
                if max_uses is not None and info["uses"] >= max_uses:
                    invites.pop(token, None)
                data["invites"] = invites
                save_data(data)
                text = (
                    "🤝 Ты вошёл по приглашению друга.\n\n"
                    "Профиль активирован, уровень доступа: <b>friend</b>.\n\n"
                    "Открывай главное меню и выбирай тайтлы."
                )
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("📚 Открыть главное меню", callback_data="main_menu")]])
                await update.effective_message.reply_text(text, reply_markup=kb)
                return

    if not user_data.get("activated", False):
        subscribed = await is_subscribed(context, user_id)
        if subscribed:
            user_data["activated"] = True
            save_data(data)
            await show_main_menu(update, context, data)
            return

        text = (
            "⚡ Перед началом нужно активировать профиль.\n\n"
            "1) Подпишись на канал AnimeHUB | Dream.\n"
            "2) Нажми кнопку «Я подписан ✅» — я проверю подписку и активирую профиль.\n\n"
            "Без активации прогресс и избранное не будут сохраняться."
        )
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🏠 Открыть канал", url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")],
                [InlineKeyboardButton("✅ Я подписан", callback_data="verify_sub")],
            ]
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
        await update.effective_message.reply_text("Введите код после команды, например:\n<code>/code AHVIP2025</code>")
        return
    code = context.args[0].strip()
    level = ACCESS_CODES.get(code)
    if not level:
        await update.effective_message.reply_text("❌ Неверный или устаревший код доступа.")
        return
    user_data["access"] = level
    save_data(data)
    await update.effective_message.reply_text(f"✅ Код принят. Новый уровень доступа: <b>{level}</b>")

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
        f"👥 Пользователей в базе: <b>{users_count}</b>",
        f"🎲 Случайный тайтл использован: <b>{data['stats']['random_used']}</b> раз",
        f"▶ Постов создано через /post: <b>{data['stats']['posts_created']}</b>",
        f"📝 Постов отредактировано через /edit_post: <b>{data['stats']['posts_edited']}</b>",
        f"🧾 Черновиков через /post_draft: <b>{data['stats']['drafts_created']}</b>",
        f"🔁 Репостов через /repost: <b>{data['stats']['reposts']}</b>",
        "\n📊 Переходы по разделам:",
    ]
    for k, v in sections.items():
        parts.append(f"• <b>{k}</b>: {v}")
    await send_with_cleanup(update, context, "\n".join(parts))

async def handle_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    if not is_admin(data, user_id):
        await update.effective_message.reply_text("Эта команда только для администратора.")
        return

    users = data.get("users", {})
    activated_users = [(uid, u) for uid, u in users.items() if u.get("activated")]
    total = len(activated_users)
    if total == 0:
        await update.effective_message.reply_text("Пока нет ни одного активированного пользователя.")
        return

    lines = [f"👥 Активированные пользователи: <b>{total}</b>"]
    for uid, u in activated_users:
        name = u.get("full_name") or f"Пользователь {uid}"
        lines.append(f"• <a href='tg://user?id={uid}'>{name}</a> — <code>{uid}</code>")
    await send_with_cleanup(update, context, "\n".join(lines))

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

    lines = ["⭐ <b>Твои избранные тайтлы:</b>"]
    for fid in favs:
        t = next((t for t in TITLES if t["id"] == fid), None)
        if t:
            lines.append(f"• <b>{t['name']}</b> — <code>/title {t['id']}</code>")
        else:
            lines.append(f"• Неизвестный тайтл: {fid}")
    await send_with_cleanup(update, context, "\n".join(lines))

async def handle_watched_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    tg_user = update.effective_user
    user_data = get_user(data, user_id)
    update_user_names(data, user_id, tg_user)

    if not context.args:
        await update.effective_message.reply_text("Использование:\n<code>/watched_add solo_leveling</code>")
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
            await update.effective_message.reply_text("Этот тайтл уже отмечен как просмотренный в списке «150 лучших аниме».")
    else:
        await update.effective_message.reply_text("Этот тайтл сейчас не помечен как часть списка «150 лучших аниме».")

async def handle_watched_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    tg_user = update.effective_user
    user_data = get_user(data, user_id)
    update_user_names(data, user_id, tg_user)

    if not context.args:
        await update.effective_message.reply_text("Использование:\n<code>/watched_remove solo_leveling</code>")
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
            msg += "\n\nДобавь просмотренный тайтл командой:\n<code>/watched_add id</code>"
        await update.effective_message.reply_text(msg)
        return

    lines = ["🏆 <b>Твой прогресс по «150 лучшим аниме»:</b>"]
    for tid in watched:
        t = next((t for t in TITLES if t["id"] == tid), None)
        if t:
            lines.append(f"• <b>{t['name']}</b> — <code>/title {t['id']}</code>")
        else:
            lines.append(f"• Неизвестный тайтл: {tid}")

    if total_top150 > 0:
        percent = round(len(watched) / total_top150 * 100, 1)
        lines.append(f"\nПрогресс: <b>{len(watched)}/{total_top150}</b> ({percent}%)")

    await send_with_cleanup(update, context, "\n".join(lines))

def weekly_rank(diff):
    if diff <= 0:
        return "Спящий наблюдатель", 1
    if diff == 1:
        return "Новичок", 2
    if 2 <= diff <= 3:
        return "Охотник", 5
    if 4 <= diff <= 6:
        return "Герой", 8
    if 7 <= diff <= 10:
        return "Легенда", 0
    return "Легенда", 0

async def handle_weekly(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    tg_user = update.effective_user
    user = get_user(data, user_id)
    update_user_names(data, user_id, tg_user)

    total = len(user.get("watched_150", []))
    base = user.get("weekly_150_start", total)
    diff = total - base
    rank, next_target = weekly_rank(diff)

    if diff <= 0:
        msg = (
            "🏆 Еженедельный прогресс по «150 лучшим аниме»\n\n"
            "За эту неделю ты не добавил новых тайтлов в список 150.\n"
            f"Текущий ранг: <b>{rank}</b>.\n\n"
            "Добавь хотя бы один тайтл и попробуй ещё раз позже."
        )
    else:
        if next_target > 0 and next_target > diff:
            need = next_target - diff
            msg_next = f"До следующего уровня осталось всего <b>{need}</b> тайтл(ов)."
        else:
            msg_next = "Ты на максимальном уровне этой недели. Жёстко."
        msg = (
            "🏆 Еженедельный прогресс по «150 лучшим аниме»\n\n"
            f"За эту неделю ты посмотрел и отметил <b>{diff}</b> новых тайтл(ов) из постера 150.\n"
            f"Текущий ранг: <b>{rank}</b>.\n\n"
            f"{msg_next}\n\n"
            f"Всего в прогрессе 150 сейчас: <b>{total}</b>."
        )

    user["weekly_150_start"] = total
    save_data(data)
    await update.effective_message.reply_text(msg)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    is_admin_user = is_admin(data, user_id)

    if is_admin_user:
        text = (
            "🛠 <b>Помощь (режим админа)</b>\n\n"
            "📌 <b>Основное</b>\n"
            "• <code>/start</code> – запустить бота\n"
            "• <code>/menu</code> – главное меню\n"
            "• <code>/help</code> – это меню\n"
            "• <code>/profile</code> – мой профиль\n"
            "• <code>/myid</code> – мой Telegram ID\n"
            "• <code>/title id</code> – карточка тайтла\n"
            "• <code>/search текст</code> – поиск по постам и тайтлам\n"
            "• <code>/code код</code> – ввести код доступа\n"
            "• <code>/weekly</code> – недельный прогресс по 150\n\n"
            "⭐ <b>Избранное и 150 лучших</b>\n"
            "• <code>/favorites</code> – избранные тайтлы\n"
            "• <code>/watched_add id</code> – добавить в «150 лучших»\n"
            "• <code>/watched_remove id</code> – убрать из «150 лучших»\n"
            "• <code>/watched_list</code> – мой прогресс 150\n\n"
            "📨 <b>Обратная связь</b>\n"
            "• <code>/suggest текст</code> – отправить предложение/фидбек админам\n\n"
            "Навигация по аниме — через кнопки под сообщениями."
        )
    else:
        text = (
            "📖 <b>Помощь по боту AnimeHUB | Dream</b>\n\n"
            "📌 <b>Основное</b>\n"
            "• <code>/start</code> – запустить бота\n"
            "• <code>/menu</code> – главное меню\n"
            "• <code>/help</code> – это меню\n"
            "• <code>/profile</code> – мой профиль\n"
            "• <code>/myid</code> – мой Telegram ID\n"
            "• <code>/title id</code> – карточка тайтла\n"
            "• <code>/search текст</code> – поиск по постам и тайтлам\n"
            "• <code>/code код</code> – ввести код доступа (если есть)\n"
            "• <code>/weekly</code> – мой недельный прогресс по 150\n\n"
            "⭐ <b>Избранное и «150 лучших»</b>\n"
            "• <code>/favorites</code> – мои избранные тайтлы\n"
            "• <code>/watched_add id</code> – добавить тайтл в прогресс 150\n"
            "• <code>/watched_remove id</code> – убрать тайтл из прогресса 150\n"
            "• <code>/watched_list</code> – показать мой прогресс 150\n\n"
            "📨 <b>Обратная связь</b>\n"
            "• <code>/suggest текст</code> – предложить тайтл или идею для канала\n\n"
            "Навигация по аниме — через кнопки под сообщениями: тайтлы, популярное, 150 лучших, полнометражки."
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
        await update.effective_message.reply_text("Использование:\n<code>/title solo_leveling</code>")
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
            "<code>/code код</code>"
        )
        return

    card = build_premium_card(title)
    await update.effective_message.reply_text(card)

async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if await abort_if_banned(update, data):
        return

    if not context.args:
        await update.effective_message.reply_text("Использование:\n<code>/search гуррен-лаганн</code>")
        return

    query = " ".join(context.args).strip().lower()
    base_link = f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"

    posts = data.get("posts", {})
    post_matches = []
    for mid, info in posts.items():
        cap = (info.get("caption") or "")
        if query in cap.lower():
            post_matches.append((int(mid), cap))

    if post_matches:
        post_matches.sort(key=lambda x: x[0])
        lines = ["🔎 <b>Найденные посты в канале:</b>"]
        for mid, cap in post_matches[:15]:
            first_line = cap.strip().splitlines()[0] if cap.strip() else f"Пост #{mid}"
            if len(first_line) > 50:
                first_line = first_line[:47] + "..."
            url = f"{base_link}/{mid}"
            lines.append(f"• <a href='{url}'>{first_line}</a>")
        await update.effective_message.reply_text("\n".join(lines))
        return

    results = []
    for t in TITLES:
        name = t.get("name", "").lower()
        tid = t.get("id", "").lower()
        if query in name or query in tid:
            results.append(t)

    if not results:
        await update.effective_message.reply_text("Ничего не найдено по этому запросу.")
        return

    if len(results) == 1:
        t = results[0]
        card = build_premium_card(t)
        await update.effective_message.reply_text(card)
        return

    lines = ["🔎 <b>Найденные тайтлы:</b>"]
    for t in results[:20]:
        lines.append(f"• <b>{t['name']}</b> — <code>/title {t['id']}</code>")
    await update.effective_message.reply_text("\n".join(lines))

async def handle_myid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    text = (
        f"Твой Telegram ID: <code>{user_id}</code>\n\n"
        "Отправь его другу, чтобы он смог добавить тебя в друзья через:\n"
        "<code>/friend_invite ID</code>"
    )
    await update.effective_message.reply_text(text)

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

    if data_str == "verify_sub":
        subscribed = await is_subscribed(context, user_id)
        if subscribed:
            user_data["activated"] = True
            save_data(data)
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("📚 Открыть главное меню", callback_data="main_menu")]])
            await query.edit_message_text(
                "✅ Подписка подтверждена, профиль активирован.\n\n"
                "Теперь можно пользоваться навигацией и сохранять прогресс.",
                reply_markup=kb,
            )
        else:
            await query.message.reply_text(
                "Я пока не вижу подписку на канал.\n\n"
                "Подпишись на AnimeHUB | Dream, подожди пару секунд и нажми кнопку ещё раз."
            )
        return

    if data_str == "main_menu":
        await show_main_menu(update, context, data)
        return

    if data_str == "suggest_info":
        await query.message.reply_text(
            "Хочешь предложить тайтл или идею для AnimeHUB | Dream?\n\n"
            "Просто напиши:\n"
            "<code>/suggest твой текст</code>\n\n"
            "Сообщение улетит прямо админам.",
            parse_mode=ParseMode.HTML,
        )
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

    if data_str.startswith("top150_"):
        try:
            _, kind, _, page_str = data_str.split("_", 3)
            page = int(page_str)
        except ValueError:
            return
        if kind not in ("poster", "merged"):
            return
        text, page, total_pages = build_top150_page_text(kind, page)
        kb = build_top150_page_keyboard(kind, page, total_pages)
        await query.edit_message_text(text, reply_markup=kb)
        return

def main() -> None:
    defaults = Defaults(parse_mode=ParseMode.HTML)
    application = Application.builder().token(BOT_TOKEN).defaults(defaults).build()

    application.add_handler(CommandHandler("start", handle_start))
    application.add_handler(CommandHandler("menu", handle_menu))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("code", handle_code))
    application.add_handler(CommandHandler("profile", handle_profile))
    application.add_handler(CommandHandler("favorites", handle_favorites))
    application.add_handler(CommandHandler("watched_add", handle_watched_add))
    application.add_handler(CommandHandler("watched_remove", handle_watched_remove))
    application.add_handler(CommandHandler("watched_list", handle_watched_list))
    application.add_handler(CommandHandler("weekly", handle_weekly))
    application.add_handler(CommandHandler("stats", handle_stats))
    application.add_handler(CommandHandler("users", handle_users))
    application.add_handler(CommandHandler("title", handle_title))
    application.add_handler(CommandHandler("search", handle_search))
    application.add_handler(CommandHandler("myid", handle_myid))
    application.add_handler(CallbackQueryHandler(handle_buttons))

    application.run_polling()

if __name__ == "__main__":
    main()
