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
import asyncio
import re
import hashlib
import logging
import secrets
from html import escape as html_escape


def _env_int_list(name: str, default: list[int]) -> list[int]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default[:]
    result = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            result.append(int(part))
        except ValueError as exc:
            raise RuntimeError(f"{name} должен содержать Telegram ID через запятую") from exc
    return result


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


CONFIG = {
    # Секреты никогда не храним в Git. BOT_TOKEN задаётся только в панели хостинга / env.
    "BOT_TOKEN": os.getenv("BOT_TOKEN", "").strip(),
    "CHANNEL_USERNAME": os.getenv("CHANNEL_USERNAME", "@AnimeHUB_Dream").strip(),
    "DATA_FILE": os.getenv("DATA_FILE", "bot_data.json").strip(),
    "TITLES_FILE": os.getenv("TITLES_FILE", "titles.json").strip(),
    # Telegram ID сам по себе не является секретом. Можно переопределить через ROOT_ADMIN_IDS.
    "ADMINS": _env_int_list("ROOT_ADMIN_IDS", [813738453]),
    "DROP_PENDING_UPDATES": _env_bool("DROP_PENDING_UPDATES", True),
}

BOT_TOKEN = CONFIG["BOT_TOKEN"]
CHANNEL_USERNAME = CONFIG["CHANNEL_USERNAME"]
DATA_FILE = CONFIG["DATA_FILE"]
TITLES_FILE = CONFIG["TITLES_FILE"]
ADMINS = CONFIG["ADMINS"]
DROP_PENDING_UPDATES = CONFIG["DROP_PENDING_UPDATES"]


TOKEN_PATTERN = re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{20,}\b")


def redact_secrets(text: str) -> str:
    if not text:
        return text
    text = TOKEN_PATTERN.sub("[REDACTED_BOT_TOKEN]", text)
    if BOT_TOKEN:
        text = text.replace(BOT_TOKEN, "[REDACTED_BOT_TOKEN]")
    return text


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact_secrets(super().format(record))


def configure_logging() -> logging.Logger:
    handler = logging.StreamHandler()
    handler.setFormatter(RedactingFormatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    # HTTP-клиент может быть очень шумным и печатать URL запросов.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    return logging.getLogger("animehub_bot")


logger = configure_logging()


def validate_runtime_config() -> None:
    if not BOT_TOKEN:
        raise RuntimeError(
            "Не задан BOT_TOKEN. Добавьте новый токен из @BotFather в переменные окружения хостинга."
        )
    if not re.fullmatch(r"\d{6,12}:[A-Za-z0-9_-]{20,}", BOT_TOKEN):
        raise RuntimeError("BOT_TOKEN имеет неверный формат. Проверьте переменную окружения BOT_TOKEN.")
    if not CHANNEL_USERNAME.startswith("@") or len(CHANNEL_USERNAME) < 2:
        raise RuntimeError("CHANNEL_USERNAME должен быть в формате @channel_username")
    if not ADMINS:
        raise RuntimeError("Не задан ни один root-admin. Укажите ROOT_ADMIN_IDS.")

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

TITLE_STATUSES = {
    "planned": "📌 В планах",
    "watching": "👀 Смотрю",
    "completed": "✅ Просмотрено",
    "dropped": "⛔ Забросил",
}
TITLE_STATUS_ORDER = ["planned", "watching", "completed", "dropped"]

DEFAULT_TITLES = [
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
        "top150": False,
        "min_access": "free",
        "hot": True,
        "added_at": int(time.time()),
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
        "Здесь появляются тайтлы, которые сейчас в фокусе: новинки, топовые релизы,\n"
        "то, что чаще всего открывают и добавляют в избранное на AnimeHUB | Dream.\n"
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
    "Laid-Back Camp (Yuru Camp) — Лагерь на свежем воздухе (Yuru Camp)",
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

# Коды доступа — тоже секреты. Старые коды из репозитория считаются скомпрометированными.
ACCESS_CODES = {}
for _env_name, _level in (("ACCESS_CODE_VIP", "vip"), ("ACCESS_CODE_FRIEND", "friend")):
    _value = os.getenv(_env_name, "").strip()
    if _value:
        ACCESS_CODES[_value] = _level


def get_access_level_for_code(code: str) -> str | None:
    # compare_digest уменьшает утечки по времени сравнения секретов.
    for expected, level in ACCESS_CODES.items():
        if secrets.compare_digest(code, expected):
            return level
    return None


def invite_storage_key(token: str) -> str:
    # В bot_data.json храним не сам invite-токен, а только его SHA-256.
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"

LAST_BOT_MESSAGE_KEY = "last_bot_message_id"

DATA_LOCK = asyncio.Lock()
TITLES_LOCK = asyncio.Lock()

TITLES_CACHE = []
TITLES_BY_ID = {}
TOP150_MAP_POSTER = {}
TOP150_MAP_MERGED = {}


def norm_title(s: str) -> str:
    s = (s or "").lower().strip()
    s = s.replace("ё", "е")
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"[^a-z0-9а-я\s\-×]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def merged_rus_title(s: str) -> str:
    if "—" in s:
        return s.split("—", 1)[1].strip()
    return s.strip()


def rebuild_top150_maps():
    global TOP150_MAP_POSTER, TOP150_MAP_MERGED
    TOP150_MAP_POSTER = {}
    TOP150_MAP_MERGED = {}

    for i, name in enumerate(TOP150_POSTER_LIST, start=1):
        TOP150_MAP_POSTER[norm_title(name)] = i

    for i, line in enumerate(TOP150_MERGED_LIST, start=1):
        ru = merged_rus_title(line)
        TOP150_MAP_MERGED[norm_title(ru)] = i


def ensure_title_top150_fields(title: dict):
    n = norm_title(title.get("name", ""))
    poster_pos = TOP150_MAP_POSTER.get(n)
    merged_pos = TOP150_MAP_MERGED.get(n)

    title["top150_poster_pos"] = poster_pos
    title["top150_merged_pos"] = merged_pos
    title["top150"] = bool(poster_pos or merged_pos)


async def load_titles() -> list[dict]:
    global TITLES_CACHE, TITLES_BY_ID
    async with TITLES_LOCK:
        if not os.path.exists(TITLES_FILE):
            rebuild_top150_maps()
            titles = DEFAULT_TITLES[:]
            for t in titles:
                ensure_title_top150_fields(t)
            tmp = TITLES_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"version": 1, "titles": titles}, f, ensure_ascii=False, indent=2)
            os.replace(tmp, TITLES_FILE)
            TITLES_CACHE = titles
            TITLES_BY_ID = {t["id"]: t for t in titles}
            return titles

        try:
            with open(TITLES_FILE, "r", encoding="utf-8") as f:
                obj = json.load(f)
        except json.JSONDecodeError:
            broken = TITLES_FILE + f".broken_{int(time.time())}"
            try:
                os.replace(TITLES_FILE, broken)
            except OSError:
                pass
            rebuild_top150_maps()
            titles = DEFAULT_TITLES[:]
            for t in titles:
                ensure_title_top150_fields(t)
            tmp = TITLES_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"version": 1, "titles": titles}, f, ensure_ascii=False, indent=2)
            os.replace(tmp, TITLES_FILE)
            TITLES_CACHE = titles
            TITLES_BY_ID = {t["id"]: t for t in titles}
            return titles

        titles = obj.get("titles", [])
        if not isinstance(titles, list):
            titles = []

        rebuild_top150_maps()
        fixed = []
        for t in titles:
            if not isinstance(t, dict):
                continue
            if "id" not in t or "name" not in t:
                continue
            ensure_title_top150_fields(t)
            if "added_at" not in t:
                t["added_at"] = int(time.time())
            if "min_access" not in t:
                t["min_access"] = "free"
            if "hot" not in t:
                t["hot"] = False
            fixed.append(t)

        TITLES_CACHE = fixed
        TITLES_BY_ID = {t["id"]: t for t in fixed}
        return fixed


async def save_titles(titles: list[dict]) -> None:
    async with TITLES_LOCK:
        rebuild_top150_maps()
        for t in titles:
            ensure_title_top150_fields(t)
        tmp = TITLES_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "titles": titles}, f, ensure_ascii=False, indent=2)
        os.replace(tmp, TITLES_FILE)
        global TITLES_CACHE, TITLES_BY_ID
        TITLES_CACHE = titles
        TITLES_BY_ID = {t["id"]: t for t in titles}


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


async def load_data():
    async with DATA_LOCK:
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

        if "stats" not in data:
            data["stats"] = base["stats"]
        if "sections" not in data["stats"]:
            data["stats"]["sections"] = {}

        for key in ["random_used", "started", "posts_created", "posts_edited", "drafts_created", "reposts"]:
            if key not in data["stats"]:
                data["stats"][key] = 0

        for k in ["friend_requests", "users", "posts", "banned", "invites"]:
            if k not in data:
                data[k] = {}

        if "admins" not in data:
            data["admins"] = ADMINS[:]
        if "version" not in data:
            data["version"] = 1

        posts = data.get("posts", {})
        for mid, info in posts.items():
            if "caption" not in info:
                info["caption"] = None
            if "title_id" not in info:
                info["title_id"] = None
        data["posts"] = posts

        return data


def set_private_permissions(path: str) -> None:
    try:
        os.chmod(path, 0o600)
    except (OSError, NotImplementedError):
        # На некоторых платформах chmod недоступен/неполон.
        pass


def rotate_backups(path: str, keep: int = 7):
    if keep <= 0:
        return
    for i in range(keep, 0, -1):
        src = f"{path}.bak{i}"
        dst = f"{path}.bak{i+1}"
        if os.path.exists(src):
            if i == keep:
                try:
                    os.remove(src)
                except OSError:
                    pass
            else:
                try:
                    os.replace(src, dst)
                except OSError:
                    pass
    if os.path.exists(path):
        try:
            with open(path, "rb") as fsrc:
                content = fsrc.read()
            backup_path = f"{path}.bak1"
            with open(backup_path, "wb") as fdst:
                fdst.write(content)
            set_private_permissions(backup_path)
        except OSError:
            pass


async def save_data(data):
    async with DATA_LOCK:
        rotate_backups(DATA_FILE, keep=7)
        tmp = DATA_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, DATA_FILE)
        set_private_permissions(DATA_FILE)


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
            "title_statuses": {},
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
        if "title_statuses" not in u or not isinstance(u["title_statuses"], dict):
            u["title_statuses"] = {}

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
    if is_root_admin(user_id):
        return False
    if is_user_banned(data, user_id):
        if update.effective_message:
            await update.effective_message.reply_text("Ты заблокирован в этом боте.")
        return True
    return False


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


def title_top150_badge(title: dict) -> str:
    p = title.get("top150_poster_pos")
    m = title.get("top150_merged_pos")
    if p and m:
        return f"🏆 Входит в 150: 📜 постер #{p} · ⭐ объединённый #{m}"
    if p:
        return f"🏆 Входит в 150: 📜 постер #{p}"
    if m:
        return f"🏆 Входит в 150: ⭐ объединённый #{m}"
    return ""


def get_title_status(user_data: dict, title_id: str) -> str | None:
    st = user_data.get("title_statuses", {}).get(title_id)
    if st in TITLE_STATUSES:
        return st
    return None


def set_title_status(user_data: dict, title_id: str, status: str):
    if "title_statuses" not in user_data or not isinstance(user_data["title_statuses"], dict):
        user_data["title_statuses"] = {}
    if status not in TITLE_STATUSES:
        return
    user_data["title_statuses"][title_id] = status


def sync_watched_150_rule_b(user_data: dict, title: dict):
    tid = title.get("id")
    if not tid:
        return
    watched = user_data.get("watched_150", [])
    if not isinstance(watched, list):
        watched = []
    st = get_title_status(user_data, tid)
    in_150 = bool(title.get("top150_poster_pos") or title.get("top150_merged_pos"))
    if not in_150:
        if tid in watched:
            watched.remove(tid)
        user_data["watched_150"] = watched
        return
    if st == "completed":
        if tid not in watched:
            watched.append(tid)
    else:
        if tid in watched:
            watched.remove(tid)
    user_data["watched_150"] = watched


def build_title_keyboard(title: dict, user_data: dict) -> InlineKeyboardMarkup:
    tid = title["id"]

    favs = user_data.get("favorites", [])
    if tid in favs:
        fav_text = "⭐ Убрать из избранного"
        fav_cb = f"fav_remove:{tid}"
    else:
        fav_text = "⭐ В избранное"
        fav_cb = f"fav_add:{tid}"

    status = get_title_status(user_data, tid) or "planned"
    status_label = TITLE_STATUSES.get(status, TITLE_STATUSES["planned"])

    kb = []
    kb.append([InlineKeyboardButton(fav_text, callback_data=fav_cb)])

    st_row = [
        InlineKeyboardButton("📌 В планах", callback_data=f"st_set:{tid}:planned"),
        InlineKeyboardButton("👀 Смотрю", callback_data=f"st_set:{tid}:watching"),
    ]
    kb.append(st_row)

    st_row2 = [
        InlineKeyboardButton("✅ Просмотрено", callback_data=f"st_set:{tid}:completed"),
        InlineKeyboardButton("⛔ Забросил", callback_data=f"st_set:{tid}:dropped"),
    ]
    kb.append(st_row2)

    if title.get("top150"):
        kb.append([InlineKeyboardButton("🏆 Засчитать в 150 (только если Просмотрено)", callback_data=f"st_set:{tid}:completed")])

    kb.append([InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(kb)


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
    keyboard = [row]
    return InlineKeyboardMarkup(keyboard)


def build_premium_card(title: dict, user_data: dict | None = None) -> str:
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

    badge = title_top150_badge(title)
    badge_line = f"{badge}\n\n" if badge else ""

    status_line = ""
    if user_data is not None:
        st = get_title_status(user_data, title["id"])
        if st:
            status_line = f"🎯 <b>Твой статус:</b> {TITLE_STATUSES.get(st, st)}\n\n"

    return (
        f"🎬 ⭐ <b>{title['name']}</b>\n"
        f"{title.get('season', 'Сезон 1')} · ТВ-сериал\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{badge_line}"
        f"{status_line}"
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


def ensure_friend_access(user_data):
    current = user_data.get("access", "free")
    if ACCESS_LEVELS.get("friend", 1) > ACCESS_LEVELS.get(current, 0):
        user_data["access"] = "friend"


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, data) -> None:
    data["stats"]["started"] += 1
    await save_data(data)
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


async def render_hot_now(titles: list[dict]) -> str:
    hot_titles = [t for t in titles if t.get("hot")]
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
        await save_data(data)
        return

    inc_section_stat(data, section_key)
    await save_data(data)

    if section_key in ("top150", "movies"):
        subscribed = await is_subscribed(context, user_id)
        if not subscribed:
            text = (
                "🔒 Этот раздел доступен только подписчикам канала AnimeHUB | Dream.\n\n"
                "Подпишись на канал, затем вернись сюда и открой раздел ещё раз."
            )
            kb = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("✅ Открыть канал", url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")],
                    [InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")],
                ]
            )
            if from_callback:
                await update.callback_query.edit_message_text(text, reply_markup=kb)
            else:
                await update.effective_message.reply_text(text, reply_markup=kb)
            return

    titles = await load_titles()

    if section_key == "hot_now":
        text = await render_hot_now(titles)
        kb = build_section_keyboard("hot_now")
        if from_callback:
            await update.callback_query.edit_message_text(text, reply_markup=kb)
        else:
            await update.effective_message.reply_text(text, reply_markup=kb)
        return

    if section_key == "titles":
        text = SECTION_TEXTS["titles"] + "\n\n" + "Чтобы открыть карточку:\n<code>/title id</code>\n\n" + "Пример:\n<code>/title solo_leveling</code>"
        kb = build_section_keyboard("titles")
        if from_callback:
            await update.callback_query.edit_message_text(text, reply_markup=kb)
        else:
            await update.effective_message.reply_text(text, reply_markup=kb)
        return

    if section_key == "movies":
        text = SECTION_TEXTS["movies"]
        kb = build_section_keyboard("movies")
        if from_callback:
            await update.callback_query.edit_message_text(text, reply_markup=kb)
        else:
            await update.effective_message.reply_text(text, reply_markup=kb)
        return

    if section_key == "top150":
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

    titles = await load_titles()

    available = []
    for t in titles:
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
    await save_data(data)
    title = random.choice(available)
    card = build_premium_card(title, user_data=user_data)
    kb = build_title_keyboard(title, user_data)
    if from_callback:
        await update.callback_query.edit_message_text(card, reply_markup=kb)
    else:
        await send_with_cleanup(update, context, card, reply_markup=kb)


async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, data, from_callback: bool) -> None:
    user_id = update.effective_user.id
    tg_user = update.effective_user
    user_data = get_user(data, user_id)
    update_user_names(data, user_id, tg_user)

    fav_count = len(user_data.get("favorites", []))
    watched_150 = len(user_data.get("watched_150", []))
    friends_count = len(user_data.get("friends", []))
    access = user_data.get("access", "free")

    titles = await load_titles()
    total_top150 = sum(1 for t in titles if t.get("top150"))

    progress = ""
    if total_top150 > 0:
        percent = round(watched_150 / total_top150 * 100, 1)
        progress = f" ({watched_150}/{total_top150}, {percent}%)"

    name_part = html_escape(user_data.get("full_name") or tg_user.first_name or "Пользователь")
    text = (
        f"👤 Профиль: <b>{name_part}</b>\n\n"
        f"🔑 Уровень доступа: <b>{access}</b>\n"
        f"⭐ Избранных тайтлов: <b>{fav_count}</b>\n"
        f"🏆 Прогресс по «150 лучшим аниме»: <b>{watched_150}</b>{progress}\n"
        f"🤝 Друзей: <b>{friends_count}</b>\n\n"
        "Статусы тайтлов:\n"
        "📌 В планах · 👀 Смотрю · ✅ Просмотрено · ⛔ Забросил\n\n"
        "Открывай карточки тайтлов и отмечай статус кнопками."
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
    data = await load_data()
    if await abort_if_banned(update, data):
        return

    await load_titles()

    user_id = update.effective_user.id
    tg_user = update.effective_user
    user_data = get_user(data, user_id)
    update_user_names(data, user_id, tg_user)
    await save_data(data)

    args = context.args
    if args:
        arg0 = args[0].strip()
        if arg0.lower() == "activate":
            user_data["activated"] = True
            await save_data(data)
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
            hashed_key = invite_storage_key(token)
            # hashed_key — новый безопасный формат; token — поддержка старых ссылок до их истечения.
            storage_key = hashed_key if hashed_key in invites else token
            info = invites.get(storage_key)
            if info and info.get("type") == "friend":
                ensure_friend_access(user_data)
                user_data["activated"] = True
                info["uses"] = info.get("uses", 0) + 1
                max_uses = info.get("max_uses")
                if max_uses is not None and info["uses"] >= max_uses:
                    invites.pop(storage_key, None)
                data["invites"] = invites
                await save_data(data)
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
            await save_data(data)
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
    data = await load_data()
    if await abort_if_banned(update, data):
        return
    await show_main_menu(update, context, data)


async def handle_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await load_data()
    if await abort_if_banned(update, data):
        return

    user_id = update.effective_user.id
    tg_user = update.effective_user
    user_data = get_user(data, user_id)
    update_user_names(data, user_id, tg_user)

    if check_rate_limit(user_id, "access_code", 2.0):
        await update.effective_message.reply_text("Слишком много попыток. Подожди немного и попробуй снова.")
        return

    if not context.args:
        await update.effective_message.reply_text("Введите код после команды, например:\n<code>/code ВАШ_КОД</code>")
        return

    code = context.args[0].strip()
    level = get_access_level_for_code(code)
    if not level:
        await update.effective_message.reply_text("❌ Неверный или устаревший код доступа.")
        return

    user_data["access"] = level
    await save_data(data)
    await update.effective_message.reply_text(f"✅ Код принят. Новый уровень доступа: <b>{level}</b>")


async def handle_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await load_data()
    if await abort_if_banned(update, data):
        return
    await show_profile(update, context, data, from_callback=False)


async def handle_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await load_data()
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
    text = "\n".join(parts)
    await send_with_cleanup(update, context, text)


async def handle_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await load_data()
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
        name = html_escape(u.get("full_name") or f"Пользователь {uid}")
        lines.append(f"• <a href='tg://user?id={uid}'>{name}</a> — <code>{uid}</code>")
    await send_with_cleanup(update, context, "\n".join(lines))


async def handle_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await load_data()
    if await abort_if_banned(update, data):
        return

    user_id = update.effective_user.id
    tg_user = update.effective_user
    user_data = get_user(data, user_id)
    update_user_names(data, user_id, tg_user)
    await save_data(data)

    favs = user_data.get("favorites", [])
    if not favs:
        await update.effective_message.reply_text(
            "У тебя пока нет избранных тайтлов.\n"
            "Открой карточку тайтла и нажми «⭐ В избранное»."
        )
        return

    titles = await load_titles()
    by_id = {t["id"]: t for t in titles}

    lines = ["⭐ <b>Твои избранные тайтлы:</b>"]
    for fid in favs:
        t = by_id.get(fid)
        if t:
            lines.append(f"• <b>{t['name']}</b> — <code>/title {t['id']}</code>")
        else:
            lines.append(f"• Неизвестный тайтл: {fid}")
    await send_with_cleanup(update, context, "\n".join(lines))


async def handle_watched_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await load_data()
    if await abort_if_banned(update, data):
        return

    user_id = update.effective_user.id
    tg_user = update.effective_user
    user_data = get_user(data, user_id)
    update_user_names(data, user_id, tg_user)

    titles = await load_titles()
    by_id = {t["id"]: t for t in titles}

    watched = user_data.get("watched_150", [])
    if not isinstance(watched, list):
        watched = []

    total_top150 = sum(1 for t in titles if t.get("top150"))
    if not watched:
        msg = "Ты пока не отметил ни одного тайтла из «150 лучших аниме» как <b>Просмотрено</b>."
        if total_top150 > 0:
            msg += "\n\nОткрой карточку тайтла и нажми «✅ Просмотрено»."
        await update.effective_message.reply_text(msg)
        return

    lines = ["🏆 <b>Твой прогресс по «150 лучшим аниме» (только Просмотрено):</b>"]
    for tid in watched:
        t = by_id.get(tid)
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
    data = await load_data()
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
            "За эту неделю ты не отметил новых тайтлов как <b>Просмотрено</b>.\n"
            f"Текущий ранг: <b>{rank}</b>.\n\n"
            "Открой тайтл из 150 и нажми «✅ Просмотрено»."
        )
    else:
        if next_target > 0 and next_target > diff:
            need = next_target - diff
            msg_next = f"До следующего уровня осталось всего <b>{need}</b> тайтл(ов)."
        else:
            msg_next = "Ты на максимальном уровне этой недели. Жёстко."
        msg = (
            "🏆 Еженедельный прогресс по «150 лучшим аниме»\n\n"
            f"За эту неделю ты отметил <b>{diff}</b> новых тайтл(ов) как <b>Просмотрено</b>.\n"
            f"Текущий ранг: <b>{rank}</b>.\n\n"
            f"{msg_next}\n\n"
            f"Всего в прогрессе 150 сейчас: <b>{total}</b>."
        )

    user["weekly_150_start"] = total
    await save_data(data)
    await update.effective_message.reply_text(msg)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await load_data()
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
            "• <code>/watched_list</code> – мой прогресс 150\n\n"
            "👥 <b>Друзья</b>\n"
            "• <code>/friend_invite</code> – добавить друга\n"
            "• <code>/invite_friend</code> – выдать приглашение уровня friend\n"
            "• <code>/friend_requests</code> – входящие заявки\n"
            "• <code>/friend_accept ID</code> – принять заявку\n"
            "• <code>/friend_list</code> – список друзей\n"
            "• <code>/friend_vs ID</code> – сравнить прогресс\n\n"
            "📨 <b>Обратная связь</b>\n"
            "• <code>/suggest текст</code> – отправить предложение админам\n\n"
            "📨 <b>Посты и канал</b>\n"
            "• <code>/post</code> – мастер поста в канал\n"
            "• <code>/post_draft</code> – черновик с подтверждением\n"
            "• <code>/edit_post ссылка/ID</code> – изменить пост\n"
            "• <code>/link_post ссылка/ID title_id</code> – привязать к тайтлу\n"
            "• <code>/repost ссылка/ID</code> – пересоздать пост в канале\n\n"
            "🧩 <b>Управление ботом</b>\n"
            "• <code>/stats</code> – статистика бота\n"
            "• <code>/users</code> – активированные пользователи\n"
            "• <code>/ban_user ID</code> – заблокировать в боте\n"
            "• <code>/unban_user ID</code> – разблокировать в боте\n"
            "• <code>/admin_list</code> – список админов\n"
            "• <code>/add_admin ID</code> – добавить админа (root)\n"
            "• <code>/remove_admin ID</code> – убрать админа (кроме root)\n\n"
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
            "• <code>/weekly</code> – мой недельный прогресс по 150\n\n"
            "⭐ <b>Избранное и «150 лучших»</b>\n"
            "• <code>/favorites</code> – мои избранные тайтлы\n"
            "• <code>/watched_list</code> – мой прогресс 150 (только Просмотрено)\n\n"
            "👥 <b>Друзья</b>\n"
            "• <code>/friend_invite</code> – добавить друга\n"
            "• <code>/invite_friend</code> – выдать другу ссылку-приглашение (уровень friend)\n"
            "• <code>/friend_requests</code> – входящие заявки\n"
            "• <code>/friend_accept ID</code> – принять заявку\n"
            "• <code>/friend_list</code> – список друзей\n"
            "• <code>/friend_vs ID</code> – сравнить прогресс по аниме\n\n"
            "📨 <b>Обратная связь</b>\n"
            "• <code>/suggest текст</code> – предложить тайтл или идею\n\n"
            "В карточке тайтла есть кнопки статусов:\n"
            "📌 В планах · 👀 Смотрю · ✅ Просмотрено · ⛔ Забросил\n"
        )

    await update.effective_message.reply_text(text)


async def handle_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await load_data()
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
    await load_titles()
    title = TITLES_BY_ID.get(tid)
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

    sync_watched_150_rule_b(user_data, title)
    await save_data(data)

    card = build_premium_card(title, user_data=user_data)
    kb = build_title_keyboard(title, user_data)
    await update.effective_message.reply_text(card, reply_markup=kb)


def parse_search_filters(raw: str) -> tuple[str, dict]:
    raw = raw.strip()
    tokens = raw.split()
    filters_out = {}
    qparts = []
    for t in tokens:
        if ":" in t:
            k, v = t.split(":", 1)
            k = k.strip().lower()
            v = v.strip()
            if k and v:
                filters_out[k] = v
        else:
            qparts.append(t)
    return " ".join(qparts).strip().lower(), filters_out


async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await load_data()
    if await abort_if_banned(update, data):
        return

    if not context.args:
        await update.effective_message.reply_text("Использование:\n<code>/search гуррен-лаганн</code>")
        return

    raw = " ".join(context.args).strip()
    query, flt = parse_search_filters(raw)
    base_link = f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"

    posts = data.get("posts", {})
    post_matches = []
    if query:
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

    titles = await load_titles()
    results = []

    for t in titles:
        name = (t.get("name") or "").lower()
        tid = (t.get("id") or "").lower()
        studio = (t.get("studio") or "").lower()
        year = (t.get("year") or "").lower()
        status = (t.get("status") or "").lower()
        genres = (t.get("genres") or "").lower()

        ok = True
        if query:
            if query not in name and query not in tid:
                ok = False

        if ok and "studio" in flt:
            if flt["studio"].lower() not in studio:
                ok = False
        if ok and "year" in flt:
            if flt["year"].lower() not in year:
                ok = False
        if ok and "status" in flt:
            if flt["status"].lower() not in status:
                ok = False
        if ok and "genre" in flt:
            if flt["genre"].lower() not in genres:
                ok = False

        if ok:
            results.append(t)

    if not results:
        await update.effective_message.reply_text("Ничего не найдено по этому запросу.")
        return

    if len(results) == 1:
        user_data = get_user(data, update.effective_user.id)
        t = results[0]
        sync_watched_150_rule_b(user_data, t)
        await save_data(data)
        card = build_premium_card(t, user_data=user_data)
        kb = build_title_keyboard(t, user_data)
        await update.effective_message.reply_text(card, reply_markup=kb)
        return

    lines = ["🔎 <b>Найденные тайтлы:</b>"]
    for t in results[:20]:
        extra = ""
        if t.get("top150"):
            p = t.get("top150_poster_pos")
            m = t.get("top150_merged_pos")
            if p and m:
                extra = f" (🏆 📜#{p} · ⭐#{m})"
            elif p:
                extra = f" (🏆 📜#{p})"
            elif m:
                extra = f" (🏆 ⭐#{m})"
        lines.append(f"• <b>{t['name']}</b>{extra} — <code>/title {t['id']}</code>")
    await update.effective_message.reply_text("\n".join(lines))


async def handle_myid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    text = (
        f"Твой Telegram ID: <code>{user_id}</code>\n\n"
        "Отправь его другу, чтобы он смог добавить тебя в друзья через:\n"
        "<code>/friend_invite ID</code>"
    )
    await update.effective_message.reply_text(text)


async def handle_friend_invite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await load_data()
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
                "Как добавить друга:\n\n"
                "• Ответь на его сообщение и напиши: <code>/friend_invite</code>\n"
                "• Или: <code>/friend_invite @username</code>\n"
                "• Или: <code>/friend_invite ссылка_на_профиль</code>\n"
                "  (например, <code>https://t.me/username</code>)\n"
                "• Или: <code>/friend_invite ID</code>\n\n"
                "ID друг может узнать командой <code>/myid</code> у себя."
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
                    "Не удалось найти пользователя по этому username/ссылке.\n\n"
                    "Убедись, что:\n"
                    "• друг уже писал этому боту\n"
                    "• указан корректный @username или ссылка вида <code>https://t.me/username</code>"
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
    await save_data(data)

    await update.effective_message.reply_text(
        "✅ Приглашение в друзья отправлено.\n"
        "Скажи другу запустить бота и набрать <code>/friend_requests</code>, чтобы принять."
    )

    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=(
                "🤝 Тебе пришло приглашение в друзья!\n\n"
                f"От пользователя: <a href='tg://user?id={from_id}'>{from_id}</a>\n\n"
                "Чтобы посмотреть и принять приглашение, набери команду:\n"
                "<code>/friend_requests</code>"
            ),
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass


async def handle_invite_friend(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await load_data()
    if await abort_if_banned(update, data):
        return

    from_id = update.effective_user.id
    user = get_user(data, from_id)
    if not user.get("activated"):
        await update.effective_message.reply_text("Сначала активируй профиль через /start, а потом создавай приглашения.")
        return

    if check_rate_limit(from_id, "invite_friend", 5.0):
        await update.effective_message.reply_text("Слишком часто создаёшь приглашения, попробуй чуть позже.")
        return

    invites = data.get("invites", {})
    while True:
        # secrets, а не random: ссылка является bearer-секретом и должна быть непредсказуемой.
        token = f"friend_{secrets.token_urlsafe(24)}"
        storage_key = invite_storage_key(token)
        if storage_key not in invites:
            break

    invites[storage_key] = {
        "type": "friend",
        "created_by": from_id,
        "created_at": int(time.time()),
        "uses": 0,
        "max_uses": 5,
    }
    data["invites"] = invites
    await save_data(data)

    bot_username = context.bot.username
    link = f"https://t.me/{bot_username}?start={token}"

    await update.effective_message.reply_text(
        "🎁 Приглашение уровня <b>friend</b> создано.\n\n"
        "Отправь эту ссылку другу. Когда он зайдёт через неё и нажмёт /start,\n"
        "его профиль автоматически активируется с уровнем доступа <b>friend</b>.\n\n"
        f"Ссылка:\n<code>{link}</code>\n\n"
        "Лимит: до 5 использований."
    )


async def handle_friend_requests(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    uid = str(user_id)
    reqs = data.get("friend_requests", {}).get(uid, [])
    if not reqs:
        await update.effective_message.reply_text("У тебя нет входящих приглашений в друзья.")
        return

    lines = ["📨 <b>Входящие приглашения в друзья:</b>"]
    for rid in reqs:
        lines.append(f"• <a href='tg://user?id={rid}'>Пользователь {rid}</a> — принять: <code>/friend_accept {rid}</code>")
    await send_with_cleanup(update, context, "\n".join(lines))


async def handle_friend_accept(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    uid = str(user_id)

    if not context.args:
        await update.effective_message.reply_text(
            "Использование:\n<code>/friend_accept ID</code>\n\n"
            "Посмотри список входящих заявок: <code>/friend_requests</code>"
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

    await save_data(data)

    await update.effective_message.reply_text(
        f"✅ Пользователь {other_id} добавлен в друзья.\n"
        f"Теперь вы можете сравнивать прогресс по аниме: <code>/friend_vs {other_id}</code>"
    )


async def handle_friend_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await load_data()
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
            "Отправь свой ID (<code>/myid</code>) другу и пусть он добавит тебя через <code>/friend_invite</code>."
        )
        return

    lines = ["🤝 <b>Твой список друзей:</b>"]
    for fid in friends:
        fdata = get_user(data, int(fid))
        name = html_escape(fdata.get("full_name") or f"Пользователь {fid}")
        lines.append(f"• <a href='tg://user?id={fid}'>{name}</a>")
    lines.append("\nЧтобы сравнить прогресс, используй:\n<code>/friend_vs ID_друга</code>")
    await send_with_cleanup(update, context, "\n".join(lines))


async def handle_friend_vs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    if not context.args:
        await update.effective_message.reply_text(
            "Использование:\n<code>/friend_vs ID_друга</code>\n\n"
            "Сначала посмотри список друзей: <code>/friend_list</code>"
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
        await update.effective_message.reply_text("Этот пользователь не в твоих друзьях.\nСначала добавь его через систему заявок.")
        return

    u_fav = len(user_data.get("favorites", []))
    o_fav = len(other_data.get("favorites", []))
    u_150 = len(user_data.get("watched_150", []))
    o_150 = len(other_data.get("watched_150", []))

    if u_fav > o_fav:
        fav_result = "По количеству тайтлов в избранном побеждаешь <b>ты</b>."
    elif u_fav < o_fav:
        fav_result = "По количеству тайтлов в избранном пока лидирует <b>твой друг</b>."
    else:
        fav_result = "По избранному у вас <b>ничья</b>."

    if u_150 > o_150:
        top_result = "По «150 лучшим аниме» побеждаешь <b>ты</b>."
    elif u_150 < o_150:
        top_result = "По «150 лучшим аниме» пока лидирует <b>твой друг</b>."
    else:
        top_result = "По «150 лучшим аниме» у вас <b>ничья</b>."

    text = (
        "⚔ <b>Сравнение аниме-прогресса</b>\n\n"
        f"Ты:\n"
        f"• Избранных тайтлов: <b>{u_fav}</b>\n"
        f"• Из «150 лучших аниме» (Просмотрено): <b>{u_150}</b>\n\n"
        f"Друг ({other_id}):\n"
        f"• Избранных тайтлов: <b>{o_fav}</b>\n"
        f"• Из «150 лучших аниме» (Просмотрено): <b>{o_150}</b>\n\n"
        f"{fav_result}\n"
        f"{top_result}"
    )
    await send_with_cleanup(update, context, text)


async def handle_suggest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await load_data()
    if await abort_if_banned(update, data):
        return
    user = update.effective_user
    uid = user.id

    if not context.args:
        await update.effective_message.reply_text(
            "Отправь предложение или идею в формате:\n"
            "<code>/suggest хочу увидеть вот такой тайтл...</code>"
        )
        return

    text = " ".join(context.args).strip()
    if not text:
        await update.effective_message.reply_text("Текст предложения пустой.")
        return

    admins_all = set(ADMINS) | set(data.get("admins", []))
    for aid in admins_all:
        try:
            await context.bot.send_message(
                chat_id=aid,
                text=(
                    "📩 <b>Новое предложение от пользователя</b>\n\n"
                    f"От: <a href='tg://user?id={uid}'>{uid}</a>\n\n"
                    f"Текст:\n{html_escape(text)}"
                ),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass

    await update.effective_message.reply_text("Спасибо! Твоё предложение отправлено админам.")


async def handle_ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await load_data()
    user_id = update.effective_user.id
    if not is_admin(data, user_id):
        await update.effective_message.reply_text("Эта команда только для админа.")
        return
    if not context.args:
        await update.effective_message.reply_text("Использование:\n<code>/ban_user ID</code>")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("ID должен быть числом.")
        return
    if is_root_admin(target_id):
        await update.effective_message.reply_text("Корневого администратора нельзя заблокировать через бота.")
        return
    tid = str(target_id)
    banned = data.get("banned", {})
    banned[tid] = True
    data["banned"] = banned
    await save_data(data)
    await update.effective_message.reply_text(f"Пользователь {target_id} заблокирован в боте.")


async def handle_unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await load_data()
    user_id = update.effective_user.id
    if not is_admin(data, user_id):
        await update.effective_message.reply_text("Эта команда только для админа.")
        return
    if not context.args:
        await update.effective_message.reply_text("Использование:\n<code>/unban_user ID</code>")
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
        await save_data(data)
        await update.effective_message.reply_text(f"Пользователь {target_id} разблокирован.")
    else:
        await update.effective_message.reply_text("Этот пользователь не был заблокирован.")


async def handle_admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    if not is_admin(data, user_id):
        await update.effective_message.reply_text("Эта команда только для админов.")
        return

    admins_file = set(data.get("admins", []))
    base_admins = set(ADMINS)
    all_admins = sorted(admins_file | base_admins)

    lines = ["🔐 <b>Список админов:</b>"]
    for aid in all_admins:
        mark = " (root)" if aid in base_admins else ""
        lines.append(f"• <a href='tg://user?id={aid}'>{aid}</a>{mark}")
    await send_with_cleanup(update, context, "\n".join(lines))


async def handle_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    if not is_root_admin(user_id):
        await update.effective_message.reply_text("Добавлять админов может только корневой админ.")
        return
    if not context.args:
        await update.effective_message.reply_text("Использование:\n<code>/add_admin ID</code>")
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
    await save_data(data)
    await update.effective_message.reply_text(f"Пользователь {target_id} добавлен в админы.")


async def handle_remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    if not is_root_admin(user_id):
        await update.effective_message.reply_text("Удалять админов может только корневой админ.")
        return
    if not context.args:
        await update.effective_message.reply_text("Использование:\n<code>/remove_admin ID</code>")
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
        await update.effective_message.reply_text("Этот пользователь не является админом (или является root через CONFIG).")
        return

    admins_list = [a for a in admins_list if a != target_id]
    data["admins"] = admins_list
    await save_data(data)
    await update.effective_message.reply_text(f"Пользователь {target_id} убран из админов.")


async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await load_data()
    if await abort_if_banned(update, data):
        return

    query = update.callback_query
    await query.answer()
    data_str = query.data

    user_id = update.effective_user.id
    tg_user = update.effective_user
    user_data = get_user(data, user_id)
    update_user_names(data, user_id, tg_user)

    await load_titles()

    if data_str == "verify_sub":
        subscribed = await is_subscribed(context, user_id)
        if subscribed:
            user_data["activated"] = True
            await save_data(data)
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("📚 Открыть главное меню", callback_data="main_menu")]])
            await query.edit_message_text(
                "✅ Подписка подтверждена, профиль активирован.\n\nТеперь можно пользоваться навигацией и сохранять прогресс.",
                reply_markup=kb,
            )
        else:
            await query.message.reply_text("Я пока не вижу подписку на канал.\n\nПодпишись, подожди пару секунд и нажми кнопку ещё раз.")
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

    if data_str == "prof_favorites":
        await handle_favorites(update, context)
        return

    if data_str == "prof_top150":
        await handle_watched_list(update, context)
        return

    if data_str == "prof_friends":
        await handle_friend_list(update, context)
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

    if data_str.startswith("fav_add:") or data_str.startswith("fav_remove:"):
        action, tid = data_str.split(":", 1)
        favs = user_data.get("favorites", [])
        if not isinstance(favs, list):
            favs = []
        if action == "fav_add":
            if tid not in favs:
                favs.append(tid)
        else:
            if tid in favs:
                favs.remove(tid)
        user_data["favorites"] = favs
        title = TITLES_BY_ID.get(tid)
        await save_data(data)
        if title:
            card = build_premium_card(title, user_data=user_data)
            kb = build_title_keyboard(title, user_data)
            await query.edit_message_text(card, reply_markup=kb)
        else:
            await query.edit_message_text("Тайтл не найден.")
        return

    if data_str.startswith("st_set:"):
        try:
            _, tid, status = data_str.split(":", 2)
        except ValueError:
            return
        title = TITLES_BY_ID.get(tid)
        if not title:
            await query.edit_message_text("Тайтл не найден.")
            return

        set_title_status(user_data, tid, status)
        sync_watched_150_rule_b(user_data, title)
        await save_data(data)

        card = build_premium_card(title, user_data=user_data)
        kb = build_title_keyboard(title, user_data)
        await query.edit_message_text(card, reply_markup=kb)
        return


POST_PHOTO, POST_CAPTION, POST_DESC, POST_WATCH = range(4)
EDIT_PHOTO, EDIT_CAPTION, EDIT_DESC, EDIT_WATCH = range(4, 8)


async def post_start_common(update: Update, context: ContextTypes.DEFAULT_TYPE, mode: str) -> int:
    data = await load_data()
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
        "Если передумал — напиши <code>/cancel</code>."
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
        "Можешь сразу вставить готовый текст из шаблона."
    )
    return POST_CAPTION


async def post_get_caption(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["post_caption"] = update.message.text or ""
    await update.effective_message.reply_text(
        "Шаг 3/4.\nВставь ссылку на описание (Telegraph).\n"
        "Если описания пока нет — напиши <code>-</code>."
    )
    return POST_DESC


async def post_get_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    desc_link = (update.message.text or "").strip()
    if desc_link == "-":
        desc_link = None
    context.user_data["post_desc_link"] = desc_link

    await update.effective_message.reply_text(
        "Шаг 4/4.\nТеперь отправь ссылку, где смотреть аниме "
        "(приватный канал/плейлист).\n"
        "Если кнопка «Смотреть» не нужна — напиши <code>-</code>."
    )
    return POST_WATCH


async def post_get_watch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    data = await load_data()
    if await abort_if_banned(update, data):
        return ConversationHandler.END
    mode = context.user_data.get("post_mode", "channel")

    watch_link = (update.message.text or "").strip()
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
                "caption": caption,
            }
            data["posts"] = posts
            await save_data(data)
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
            await save_data(data)

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
    data = await load_data()
    if await abort_if_banned(update, data):
        return ConversationHandler.END
    user_id = update.effective_user.id
    if not is_admin(data, user_id):
        await update.effective_message.reply_text("Эта команда только для админа.")
        return ConversationHandler.END

    if check_rate_limit(user_id, "edit_post", 3.0):
        await update.effective_message.reply_text("Слишком часто используешь эту команду, попробуй чуть позже.")
        return ConversationHandler.END

    if not context.args:
        await update.effective_message.reply_text("Использование:\n<code>/edit_post https://t.me/AnimeHUB_Dream/16</code>")
        return ConversationHandler.END

    msg_id = parse_message_id(context.args[0])
    if msg_id is None:
        await update.effective_message.reply_text("Не удалось понять ID сообщения. Проверь ссылку.")
        return ConversationHandler.END

    context.user_data["edit_msg_id"] = msg_id

    await update.effective_message.reply_text(
        f"Редактирование поста с ID <code>{msg_id}</code>.\n\n"
        "Шаг 1/4.\n"
        "Отправь новую обложку как фото, если хочешь заменить картинку.\n"
        "Если обложку менять не нужно — напиши <code>-</code>.\n\n"
        "Если что, <code>/cancel</code> отменит операцию."
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
            await update.effective_message.reply_text("Отправь фото или напиши <code>-</code>, если не хочешь менять обложку.")
            return EDIT_PHOTO

    await update.effective_message.reply_text("Шаг 2/4.\nОтправь новый текст подписи для поста.")
    return EDIT_CAPTION


async def edit_post_get_caption(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    caption = update.message.text or ""
    context.user_data["edit_caption"] = caption.strip()
    await update.effective_message.reply_text(
        "Шаг 3/4.\n"
        "Отправь ссылку на описание (Telegraph).\n"
        "Если описания не нужно — напиши <code>-</code>."
    )
    return EDIT_DESC


async def edit_post_get_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    desc_link = (update.message.text or "").strip()
    if desc_link == "-":
        desc_link = None
    context.user_data["edit_desc_link"] = desc_link
    await update.effective_message.reply_text(
        "Шаг 4/4.\n"
        "Отправь ссылку, где смотреть аниме (кнопка «Смотреть»).\n"
        "Если кнопка не нужна — напиши <code>-</code>."
    )
    return EDIT_WATCH


async def edit_post_get_watch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    data = await load_data()
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
        except Exception:
            logger.exception("Не удалось отредактировать пост %s", msg_id)
            await update.effective_message.reply_text(
                "Не удалось отредактировать пост. Проверь права бота в канале и корректность ID сообщения. "
                "Технические детали записаны в серверный лог."
            )
            for key in ["edit_msg_id", "edit_photo", "edit_caption", "edit_desc_link"]:
                context.user_data.pop(key, None)
            return ConversationHandler.END

        posts = data.get("posts", {})
        info = posts.get(str(msg_id), {})
        info.setdefault("title_id", None)
        info.setdefault("created_at", int(time.time()))
        info["caption"] = new_caption
        posts[str(msg_id)] = info
        data["posts"] = posts

        data["stats"]["posts_edited"] += 1
        await save_data(data)

        for key in ["edit_msg_id", "edit_photo", "edit_caption", "edit_desc_link"]:
            context.user_data.pop(key, None)

        await update.effective_message.reply_text("Пост успешно отредактирован ✅")
        return ConversationHandler.END
    finally:
        HEAVY_ACTIVE -= 1


async def handle_link_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    if not is_admin(data, user_id):
        await update.effective_message.reply_text("Эта команда только для админа.")
        return

    if len(context.args) < 2:
        await update.effective_message.reply_text(
            "Использование:\n"
            "<code>/link_post https://t.me/AnimeHUB_Dream/16 solo_leveling</code>"
        )
        return

    msg_id = parse_message_id(context.args[0])
    if msg_id is None:
        await update.effective_message.reply_text("Не удалось понять ID сообщения. Проверь ссылку.")
        return

    tid = context.args[1].strip().lower()
    await load_titles()
    title = TITLES_BY_ID.get(tid)
    if not title:
        await update.effective_message.reply_text("❌ Тайтл с таким ID не найден.")
        return

    posts = data.get("posts", {})
    info = posts.get(str(msg_id), {})
    info["title_id"] = tid
    info.setdefault("created_at", int(time.time()))
    info.setdefault("caption", None)
    posts[str(msg_id)] = info
    data["posts"] = posts
    await save_data(data)

    await update.effective_message.reply_text(f"Пост с ID <code>{msg_id}</code> привязан к тайтлу «{title['name']}».")


async def handle_repost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await load_data()
    if await abort_if_banned(update, data):
        return
    user_id = update.effective_user.id
    if not is_admin(data, user_id):
        await update.effective_message.reply_text("Эта команда только для админа.")
        return

    if not context.args:
        await update.effective_message.reply_text("Использование:\n<code>/repost https://t.me/AnimeHUB_Dream/16</code>")
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
        except Exception:
            logger.exception("Не удалось пересоздать пост %s", msg_id)
            await update.effective_message.reply_text(
                "Не удалось пересоздать пост. Проверь права бота и ID сообщения. "
                "Технические детали записаны в серверный лог."
            )
            return

        posts = data.get("posts", {})
        old_info = posts.get(str(msg_id), {})
        posts[str(m.message_id)] = {
            "title_id": old_info.get("title_id"),
            "created_at": int(time.time()),
            "caption": old_info.get("caption"),
        }
        data["stats"]["reposts"] += 1
        data["stats"]["posts_created"] += 1
        data["posts"] = posts
        await save_data(data)

        await update.effective_message.reply_text(f"Пост пересоздан в канале ✅\nНовый ID: <code>{m.message_id}</code>")
    finally:
        HEAVY_ACTIVE -= 1


async def handle_unexpected_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Необработанная ошибка при обработке update", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "Произошла внутренняя ошибка. Детали сохранены в серверном логе."
            )
        except Exception:
            logger.exception("Не удалось отправить пользователю сообщение об ошибке")


def main() -> None:
    validate_runtime_config()
    defaults = Defaults(parse_mode=ParseMode.HTML)

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .defaults(defaults)
        # ConversationHandler и операции с JSON-файлами безопаснее выполнять последовательно.
        .concurrent_updates(False)
        .build()
    )

    conv_post = ConversationHandler(
        entry_points=[
            CommandHandler("post", post_start),
            CommandHandler("post_draft", post_start_draft),
        ],
        states={
            POST_PHOTO: [MessageHandler(filters.PHOTO & ~filters.COMMAND, post_get_photo)],
            POST_CAPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, post_get_caption)],
            POST_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, post_get_desc)],
            POST_WATCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, post_get_watch)],
        },
        fallbacks=[CommandHandler("cancel", post_cancel)],
    )

    conv_edit = ConversationHandler(
        entry_points=[CommandHandler("edit_post", edit_post_start)],
        states={
            EDIT_PHOTO: [MessageHandler((filters.PHOTO | filters.TEXT) & ~filters.COMMAND, edit_post_get_photo)],
            EDIT_CAPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_post_get_caption)],
            EDIT_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_post_get_desc)],
            EDIT_WATCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_post_get_watch)],
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
    application.add_handler(CommandHandler("watched_list", handle_watched_list))
    application.add_handler(CommandHandler("weekly", handle_weekly))
    application.add_handler(CommandHandler("stats", handle_stats))
    application.add_handler(CommandHandler("users", handle_users))
    application.add_handler(CommandHandler("title", handle_title))
    application.add_handler(CommandHandler("search", handle_search))
    application.add_handler(CommandHandler("myid", handle_myid))
    application.add_handler(CommandHandler("friend_invite", handle_friend_invite))
    application.add_handler(CommandHandler("invite_friend", handle_invite_friend))
    application.add_handler(CommandHandler("friend_requests", handle_friend_requests))
    application.add_handler(CommandHandler("friend_accept", handle_friend_accept))
    application.add_handler(CommandHandler("friend_list", handle_friend_list))
    application.add_handler(CommandHandler("friend_vs", handle_friend_vs))
    application.add_handler(CommandHandler("suggest", handle_suggest))
    application.add_handler(CommandHandler("link_post", handle_link_post))
    application.add_handler(CommandHandler("repost", handle_repost))
    application.add_handler(CommandHandler("ban_user", handle_ban_user))
    application.add_handler(CommandHandler("unban_user", handle_unban_user))
    application.add_handler(CommandHandler("admin_list", handle_admin_list))
    application.add_handler(CommandHandler("add_admin", handle_add_admin))
    application.add_handler(CommandHandler("remove_admin", handle_remove_admin))
    application.add_handler(CallbackQueryHandler(handle_buttons))
    application.add_error_handler(handle_unexpected_error)

    if not ACCESS_CODES:
        logger.warning(
            "ACCESS_CODE_VIP / ACCESS_CODE_FRIEND не заданы: команда /code не выдаст повышенный доступ."
        )

    application.run_polling(drop_pending_updates=DROP_PENDING_UPDATES)


if __name__ == "__main__":
    main()