from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
)
from telegram.constants import ParseMode
from telegram.error import InvalidToken
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
import shutil
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


DATA_DIR = os.getenv("DATA_DIR", ".").strip() or "."

CONFIG = {
    # Секреты никогда не храним в Git. BOT_TOKEN задаётся только в панели хостинга / env.
    "BOT_TOKEN": os.getenv("BOT_TOKEN", "").strip(),
    "CHANNEL_USERNAME": os.getenv("CHANNEL_USERNAME", "@AnimeHUB_Dream").strip(),
    # BotHost использует DATA_DIR=/app/data как постоянное хранилище.
    # DATA_FILE/TITLES_FILE при необходимости можно переопределить отдельно.
    "DATA_DIR": DATA_DIR,
    "DATA_FILE": os.getenv("DATA_FILE", os.path.join(DATA_DIR, "bot_data.json")).strip(),
    "TITLES_FILE": os.getenv("TITLES_FILE", os.path.join(DATA_DIR, "titles.json")).strip(),
    # Telegram ID сам по себе не является секретом. Можно переопределить через ROOT_ADMIN_IDS.
    "ADMINS": _env_int_list("ROOT_ADMIN_IDS", [813738453]),
    "DROP_PENDING_UPDATES": _env_bool("DROP_PENDING_UPDATES", True),
}

BOT_TOKEN = CONFIG["BOT_TOKEN"]
CHANNEL_USERNAME = CONFIG["CHANNEL_USERNAME"]
DATA_DIR = CONFIG["DATA_DIR"]
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
BOT_STARTED_AT = time.time()


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

    # Подготавливаем директории постоянных данных до запуска Telegram polling.
    for storage_path in (DATA_FILE, TITLES_FILE):
        parent = os.path.dirname(os.path.abspath(storage_path))
        try:
            os.makedirs(parent, exist_ok=True)
        except OSError as exc:
            raise RuntimeError(
                f"Не удалось подготовить директорию данных: {parent}"
            ) from exc

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

CATALOG_SEED_VERSION = 20260927
CATALOG_PAGE_SIZE = 10

def _catalog_seed_title(tid: str, name: str, post_id: int, has_4k: bool, aliases: list[str] | None = None, **extra) -> dict:
    item = {
        "id": tid,
        "name": name,
        "season": "-",
        "status": "-",
        "episodes": "-",
        "year": "-",
        "studio": "-",
        "author": "-",
        "director": "-",
        "voice": "-",
        "shiki": "-",
        "imdb": "-",
        "kp": "-",
        "genres": "-",
        "playlist": "-",
        "desc": "-",
        "min_access": "free",
        "hot": False,
        "added_at": post_id,
        "channel_post_id": post_id,
        "has_4k": bool(has_4k),
        "aliases": list(aliases or []),
        "catalog_seed_version": CATALOG_SEED_VERSION,
    }
    item.update(extra)
    return item

CATALOG_SEED = [
    _catalog_seed_title('solo_leveling', 'Поднятие уровня в одиночку', 41, True, aliases=[]),
    _catalog_seed_title('ah42', 'Тетрадь Смерти', 42, True, aliases=[]),
    _catalog_seed_title('ah43', 'Гуррен-Лаганн, пронзающий небеса', 43, True, aliases=['Гуррен-Лаганн', 'Tengen Toppa Gurren Lagann']),
    _catalog_seed_title('ah44', 'Созданный в Бездне', 44, True, aliases=[]),
    _catalog_seed_title('ah45', 'Евангелион нового поколения', 45, True, aliases=[]),
    _catalog_seed_title('ah46', 'Ученик чудовища', 46, True, aliases=[]),
    _catalog_seed_title('ah47', 'Твоё имя', 47, True, aliases=[]),
    _catalog_seed_title('ah48', 'Провожающая в последний путь Фрирен', 48, True, aliases=[]),
    _catalog_seed_title('ah49', 'Эксперименты Лэйн', 49, True, aliases=[]),
    _catalog_seed_title('ah50', 'Берсерк (1997)', 50, True, aliases=[]),
    _catalog_seed_title('ah51', 'Человек-Бензопила', 51, True, aliases=['Человек бензопила', 'Chainsaw Man']),
    _catalog_seed_title('ah52', 'Ковбой Бибоп', 52, True, aliases=[]),
    _catalog_seed_title('ah53', 'Дорохедоро', 53, True, aliases=[]),
    _catalog_seed_title('ah54', 'Токийский гуль', 54, True, aliases=[]),
    _catalog_seed_title('ah55', 'Гачиакута', 55, True, aliases=[]),
    _catalog_seed_title('ah57', 'Подземелье вкусностей', 57, True, aliases=[]),
    _catalog_seed_title('ah60', 'Чёрный Клевер', 60, True, aliases=['Black Clover']),
    _catalog_seed_title('ah63', 'Врата Штейна', 63, False, aliases=['Steins;Gate']),
    _catalog_seed_title('ah64', 'Re:Zero. Жизнь в альтернативном мире с нуля', 64, True, aliases=['РеЗеро. Жизнь с нуля в альтернативном мире', 'Re:Zero']),
    _catalog_seed_title('ah65', 'Магическая битва', 65, True, aliases=[]),
    _catalog_seed_title('ah66', 'Эхо Террора', 66, True, aliases=[]),
    _catalog_seed_title('ah67', 'Моя геройская академия', 67, True, aliases=[]),
    _catalog_seed_title('ah69', 'Санда', 69, True, aliases=[]),
    _catalog_seed_title('ah70', 'Блич', 70, True, aliases=[]),
    _catalog_seed_title('ah71', 'Эта фарфоровая кукла влюбилась', 71, True, aliases=['My Dress-Up Darling']),
    _catalog_seed_title('ah72', 'Необъятный океан', 72, True, aliases=['Grand Blue']),
    _catalog_seed_title('ah73', 'Лазарь', 73, True, aliases=[]),
    _catalog_seed_title('ah74', 'Иллюзия рая', 74, True, aliases=[]),
    _catalog_seed_title('ah75', 'Раб спецотряда демонического города', 75, True, aliases=[]),
    _catalog_seed_title('ah76', 'Звёздное дитя', 76, True, aliases=['Ребёнок идола', 'Oshi no Ko']),
    _catalog_seed_title('ah78', 'Киберпанк: Бегущие по краю', 78, True, aliases=[]),
    _catalog_seed_title('ah79', 'Ван-Пис', 79, True, aliases=[]),
    _catalog_seed_title('ah80', 'Доктор Стоун', 80, True, aliases=[]),
    _catalog_seed_title('ah82', 'Монолог фармацевта', 82, True, aliases=[]),
    _catalog_seed_title('ah83', 'Девочка-волшебница Мадока', 83, True, aliases=['Девочка-волшебница Мадока Магика', 'Puella Magi Madoka Magica']),
    _catalog_seed_title('ah84', 'Невероятные приключения ДжоДжо', 84, True, aliases=[]),
    _catalog_seed_title('ah85', 'Приговорённый быть героем: Тюремные записи девять тысяч четвёртого штрафного отряда героев', 85, True, aliases=[]),
    _catalog_seed_title('ah86', 'Наруто', 86, True, aliases=[]),
    _catalog_seed_title('ah87', 'Пламенная бригада пожарных', 87, True, aliases=[]),
    _catalog_seed_title('ah88', 'Моб Психо 100', 88, True, aliases=[]),
    _catalog_seed_title('ah90', 'Семья шпиона', 90, True, aliases=[]),
    _catalog_seed_title('ah91', 'Адский рай', 91, True, aliases=[]),
    _catalog_seed_title('ah92', 'Повелитель', 92, True, aliases=[]),
    _catalog_seed_title('ah93', 'Монстр', 93, True, aliases=[]),
    _catalog_seed_title('ah94', 'Лето, когда умер Хикару', 94, True, aliases=[]),
    _catalog_seed_title('ah95', 'Стальной Алхимик', 95, True, aliases=[]),
    _catalog_seed_title('ah96', 'Стальной Алхимик: Братство', 96, True, aliases=['Fullmetal Alchemist: Brotherhood']),
    _catalog_seed_title('ah97', 'Хантер × Хантер', 97, True, aliases=['Хантер Х Хантер', 'Охотник × Охотник', 'Hunter x Hunter']),
    _catalog_seed_title('ah98', 'Крутой учитель Онидзука', 98, True, aliases=[]),
    _catalog_seed_title('ah100', 'Дьявол может плакать', 100, True, aliases=[]),
    _catalog_seed_title('ah101', 'Форма голоса', 101, True, aliases=[]),
    _catalog_seed_title('ah102', 'Ванпанчмен', 102, True, aliases=[]),
    _catalog_seed_title('ah104', 'Сага о Винланде', 104, True, aliases=[]),
    _catalog_seed_title('ah105', 'Дороро', 105, True, aliases=[]),
    _catalog_seed_title('ah106', 'Самурай Чамплу', 106, True, aliases=[]),
    _catalog_seed_title('ah107', 'Реинкарнация безработного: История о приключениях в другом мире', 107, True, aliases=['Реинкарнация безработного', 'Mushoku Tensei']),
    _catalog_seed_title('ah109', 'Афросамурай', 109, True, aliases=[]),
    _catalog_seed_title('ah110', 'История о перекуре за супермаркетом', 110, True, aliases=[]),
    _catalog_seed_title('ah111', 'Боевой петух', 111, True, aliases=[]),
    _catalog_seed_title('ah112', 'Нет игры — нет жизни', 112, True, aliases=['No Game No Life']),
    _catalog_seed_title('ah113', 'Убийца Акамэ!', 113, True, aliases=[]),
    _catalog_seed_title('ah114', 'Восемьдесят шесть', 114, True, aliases=['86 Eighty-Six']),
    _catalog_seed_title('ah115', 'Последний Серафим', 115, True, aliases=[]),
    _catalog_seed_title('ah116', 'Милый во Франксе', 116, True, aliases=[]),
    _catalog_seed_title('ah121', 'Ателье колдовских колпаков', 121, True, aliases=[]),
    _catalog_seed_title('ah124', 'Кайдзю №8', 124, True, aliases=['Кайдзю номер восемь', 'Kaiju No. 8']),
    _catalog_seed_title('ah126', 'Ветролом', 126, True, aliases=[]),
    _catalog_seed_title('ah127', 'Реинкарнация безработного: История о приключениях в другом мире (Обновлённая версия)', 127, True, aliases=['Реинкарнация безработного', 'Mushoku Tensei'], top150_exclude=True),
    _catalog_seed_title('ah128', 'Драконий жемчуг', 128, True, aliases=['Драгонбол', 'Dragon Ball']),
    _catalog_seed_title('ah129', 'Неуязвимый', 129, True, aliases=[]),
    _catalog_seed_title('ah130', 'Город, в котором меня нет', 130, True, aliases=[]),
    _catalog_seed_title('ah131', 'Вайолет Эвергарден', 131, True, aliases=[]),
    _catalog_seed_title('ah132', 'Кабанэри железной крепости', 132, True, aliases=[]),
    _catalog_seed_title('ah133', 'Ниндзя Камуи', 133, True, aliases=[]),
    _catalog_seed_title('ah134', 'Патриотизм Мориарти', 134, True, aliases=[]),
    _catalog_seed_title('ah135', 'О движении Земли', 135, True, aliases=[]),
    _catalog_seed_title('ah137', 'Благоухающий цветок расцветает с достоинством', 137, True, aliases=[]),
    _catalog_seed_title('ah138', 'Золотое божество', 138, True, aliases=[]),
]

# Сохраняем уже заполненную карточку Solo Leveling из прежней версии проекта.
CATALOG_SEED[0].update({
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
    "hot": True,
})

DEFAULT_TITLES = CATALOG_SEED

SECTION_TEXTS = {
    "titles": (
        "📚 Раздел «Аниме по тайтлам»\n\n"
        "Полный каталог AnimeHUB | Dream. Выбирай тайтл кнопкой — бот покажет карточку, "
        "статус 4K, прогресс и прямую ссылку на пост в канале."
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


def title_channel_url(title: dict) -> str | None:
    explicit = str(title.get("channel_post_url") or "").strip()
    if explicit.startswith(("https://", "http://")):
        return explicit
    post_id = title.get("channel_post_id")
    try:
        post_id = int(post_id)
    except (TypeError, ValueError):
        return None
    return f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}/{post_id}"


def _catalog_names(title: dict) -> list[str]:
    values = [str(title.get("name") or "")]
    aliases = title.get("aliases", [])
    if isinstance(aliases, list):
        values.extend(str(x) for x in aliases if x)
    return [x for x in values if x]


def ensure_title_top150_fields(title: dict):
    if title.get("top150_exclude"):
        title["top150_poster_pos"] = None
        title["top150_merged_pos"] = None
        title["top150"] = False
        return

    poster_pos = None
    merged_pos = None
    for candidate in _catalog_names(title):
        n = norm_title(candidate)
        if poster_pos is None:
            poster_pos = TOP150_MAP_POSTER.get(n)
        if merged_pos is None:
            merged_pos = TOP150_MAP_MERGED.get(n)
        if poster_pos and merged_pos:
            break

    title["top150_poster_pos"] = poster_pos
    title["top150_merged_pos"] = merged_pos
    title["top150"] = bool(poster_pos or merged_pos)


def _placeholder_value(value) -> bool:
    return value is None or str(value).strip() in {"", "-", "----", "?", "??"}


def merge_catalog_seed(existing: list[dict]) -> tuple[list[dict], bool]:
    """Добавляет официальный каталог в существующий titles.json без стирания заполненных метаданных."""
    changed = False
    by_id = {str(t.get("id")): t for t in existing if t.get("id")}
    by_post = {}
    by_name = {}
    for t in existing:
        try:
            pid = int(t.get("channel_post_id"))
            by_post[pid] = t
        except (TypeError, ValueError):
            pass
        by_name.setdefault(norm_title(t.get("name", "")), t)

    for seed in CATALOG_SEED:
        target = by_id.get(seed["id"])
        if target is None:
            target = by_post.get(seed["channel_post_id"])
        if target is None:
            target = by_name.get(norm_title(seed.get("name", "")))

        if target is None:
            target = dict(seed)
            target["aliases"] = list(seed.get("aliases", []))
            existing.append(target)
            by_id[target["id"]] = target
            by_post[target["channel_post_id"]] = target
            by_name.setdefault(norm_title(target.get("name", "")), target)
            changed = True
            continue

        # Эти поля являются фактами из актуального списка канала и синхронизируются всегда.
        for key in ("name", "channel_post_id", "has_4k", "catalog_seed_version", "top150_exclude"):
            if key == "channel_post_id" and target.get("channel_post_deleted"):
                continue
            if key in seed and target.get(key) != seed.get(key):
                target[key] = seed.get(key)
                changed = True
        if target.get("aliases") != seed.get("aliases"):
            current_aliases = target.get("aliases") if isinstance(target.get("aliases"), list) else []
            merged_aliases = list(dict.fromkeys([*current_aliases, *seed.get("aliases", [])]))
            if target.get("aliases") != merged_aliases:
                target["aliases"] = merged_aliases
                changed = True

        # Заполняем только пустые поля, чтобы не перетирать уже отредактированные карточки.
        for key, value in seed.items():
            if key in {"id", "name", "channel_post_id", "has_4k", "aliases", "catalog_seed_version", "top150_exclude"}:
                continue
            if key not in target or _placeholder_value(target.get(key)):
                if not _placeholder_value(value):
                    target[key] = value
                    changed = True

        target.setdefault("min_access", "free")
        target.setdefault("hot", False)
        target.setdefault("added_at", seed.get("added_at", int(time.time())))
        target.setdefault("has_4k", False)
        target.setdefault("aliases", [])

    return existing, changed


async def load_titles() -> list[dict]:
    global TITLES_CACHE, TITLES_BY_ID
    async with TITLES_LOCK:
        rebuild_top150_maps()
        changed = False

        if not os.path.exists(TITLES_FILE):
            titles = []
        else:
            try:
                with open(TITLES_FILE, "r", encoding="utf-8") as f:
                    obj = json.load(f)
                titles = obj.get("titles", [])
                if not isinstance(titles, list):
                    titles = []
                    changed = True
            except json.JSONDecodeError:
                broken = TITLES_FILE + f".broken_{int(time.time())}"
                try:
                    os.replace(TITLES_FILE, broken)
                except OSError:
                    pass
                titles = []
                changed = True

        fixed = []
        for t in titles:
            if not isinstance(t, dict) or "id" not in t or "name" not in t:
                changed = True
                continue
            if "added_at" not in t:
                t["added_at"] = int(time.time())
                changed = True
            if "min_access" not in t:
                t["min_access"] = "free"
                changed = True
            if "hot" not in t:
                t["hot"] = False
                changed = True
            if "has_4k" not in t:
                t["has_4k"] = False
                changed = True
            if "aliases" not in t or not isinstance(t.get("aliases"), list):
                t["aliases"] = []
                changed = True
            fixed.append(t)

        fixed, seed_changed = merge_catalog_seed(fixed)
        changed = changed or seed_changed

        for t in fixed:
            old_top = (t.get("top150_poster_pos"), t.get("top150_merged_pos"), t.get("top150"))
            ensure_title_top150_fields(t)
            new_top = (t.get("top150_poster_pos"), t.get("top150_merged_pos"), t.get("top150"))
            if old_top != new_top:
                changed = True

        if changed or not os.path.exists(TITLES_FILE):
            tmp = TITLES_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"version": 2, "catalog_seed_version": CATALOG_SEED_VERSION, "titles": fixed}, f, ensure_ascii=False, indent=2)
            os.replace(tmp, TITLES_FILE)
            set_private_permissions(TITLES_FILE)

        TITLES_CACHE = fixed
        TITLES_BY_ID = {t["id"]: t for t in fixed}
        return fixed


async def save_titles(titles: list[dict]) -> None:
    async with TITLES_LOCK:
        rebuild_top150_maps()
        for t in titles:
            t.setdefault("has_4k", False)
            t.setdefault("aliases", [])
            ensure_title_top150_fields(t)
        tmp = TITLES_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"version": 2, "catalog_seed_version": CATALOG_SEED_VERSION, "titles": titles}, f, ensure_ascii=False, indent=2)
        os.replace(tmp, TITLES_FILE)
        set_private_permissions(TITLES_FILE)
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
            "broadcasts_sent": 0,
            "broadcast_recipients": 0,
        },
        "friend_requests": {},
        "posts": {},
        "banned": {},
        "admins": ADMINS[:],
        "invites": {},
        "suggestions": {},
        "audit_log": [],
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

        for key in ["random_used", "started", "posts_created", "posts_edited", "drafts_created", "reposts", "broadcasts_sent", "broadcast_recipients"]:
            if key not in data["stats"]:
                data["stats"][key] = 0

        for k in ["friend_requests", "users", "posts", "banned", "invites", "suggestions"]:
            if k not in data:
                data[k] = {}

        if "admins" not in data:
            data["admins"] = ADMINS[:]
        if "audit_log" not in data or not isinstance(data["audit_log"], list):
            data["audit_log"] = []
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

    kb = [[InlineKeyboardButton(fav_text, callback_data=fav_cb)]]

    post_url = title_channel_url(title)
    if post_url:
        quality = "💠 4K" if title.get("has_4k") else "📺 Пост"
        kb.append([InlineKeyboardButton(f"{quality} · Открыть в канале", url=post_url)])

    kb.append(
        [
            InlineKeyboardButton("📌 В планах", callback_data=f"st_set:{tid}:planned"),
            InlineKeyboardButton("👀 Смотрю", callback_data=f"st_set:{tid}:watching"),
        ]
    )
    kb.append(
        [
            InlineKeyboardButton("✅ Просмотрено", callback_data=f"st_set:{tid}:completed"),
            InlineKeyboardButton("⛔ Забросил", callback_data=f"st_set:{tid}:dropped"),
        ]
    )

    if title.get("top150"):
        kb.append([InlineKeyboardButton("🏆 Засчитать в 150 (Просмотрено)", callback_data=f"st_set:{tid}:completed")])

    kb.append([InlineKeyboardButton("📚 К каталогу", callback_data="catpage:1")])
    kb.append([InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(kb)


def build_main_menu_keyboard(is_admin_user: bool = False) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📚 Аниме по тайтлам", callback_data="sec_titles")],
        [InlineKeyboardButton("🔥 Популярно сейчас", callback_data="sec_hot_now")],
        [InlineKeyboardButton("🏆 150 лучших аниме", callback_data="sec_top150")],
        [InlineKeyboardButton("🎬 Полнометражки", callback_data="sec_movies")],
        [InlineKeyboardButton("🎲 Случайный тайтл", callback_data="rand_title")],
        [InlineKeyboardButton("👤 Мой профиль", callback_data="my_profile")],
        [InlineKeyboardButton("📩 Предложить тайтл", callback_data="suggest_info")],
    ]
    if is_admin_user:
        keyboard.append([InlineKeyboardButton("🛠 Админ-панель", callback_data="adm:home")])
    keyboard.append(
        [
            InlineKeyboardButton(
                "🏠 Открыть канал",
                url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}",
            )
        ]
    )
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


def _card_value(value) -> str:
    if _placeholder_value(value):
        return ""
    return html_escape(str(value))


def build_premium_card(title: dict, user_data: dict | None = None) -> str:
    access = title.get("min_access", "free")
    access_label = {
        "free": "Открыт для всех",
        "friend": "Доступ для друзей",
        "vip": "VIP-доступ",
    }.get(access, "Ограниченный доступ")

    badge = title_top150_badge(title)
    st = get_title_status(user_data, title["id"]) if user_data is not None else None
    post_id = title.get("channel_post_id")
    has_4k = bool(title.get("has_4k"))

    lines = [f"🎬 ⭐ <b>{html_escape(str(title.get('name', 'Без названия')))}</b>"]
    season = _card_value(title.get("season"))
    if season:
        lines.append(season)
    lines.extend(["", "━━━━━━━━━━━━━━━━━━━━", ""])

    if badge:
        lines.extend([badge, ""])
    if st:
        lines.extend([f"🎯 <b>Твой статус:</b> {TITLE_STATUSES.get(st, st)}", ""])

    info = []
    for icon, label, key in (
        ("📅", "Статус", "status"),
        ("🎞", "Эпизодов", "episodes"),
        ("📆", "Год", "year"),
        ("🏢", "Студия", "studio"),
        ("✍", "Автор", "author"),
        ("🎬", "Режиссёр", "director"),
        ("🔊", "Озвучки", "voice"),
    ):
        value = _card_value(title.get(key))
        if value:
            info.append(f"{icon} {label}: {value}")
    if info:
        lines.extend(["📌 <b>Информация</b>", *info, "", "━━━━━━━━━━━━━━━━━━━━", ""])

    ratings = []
    for icon, label, key in (("📈", "Shikimori", "shiki"), ("🍿", "IMDb", "imdb"), ("🎥", "Кинопоиск", "kp")):
        value = _card_value(title.get(key))
        if value:
            ratings.append(f"{icon} {label}: {value}")
    if ratings:
        lines.extend(["📊 <b>Рейтинги</b>", *ratings, "", "━━━━━━━━━━━━━━━━━━━━", ""])

    genres = _card_value(title.get("genres"))
    if genres:
        lines.extend(["🏷 <b>Жанры</b>", format_genres(genres, max_tags=6, line_limit=60), "", "━━━━━━━━━━━━━━━━━━━━", ""])

    playlist = _card_value(title.get("playlist"))
    if playlist:
        lines.extend(["📂 <b>Сезоны / Плейлисты</b>", playlist, "", "━━━━━━━━━━━━━━━━━━━━", ""])

    desc = _card_value(title.get("desc"))
    if desc:
        lines.extend(["📝 <b>Описание</b>", desc, "", "━━━━━━━━━━━━━━━━━━━━", ""])

    lines.append(f"🔑 Доступ: {access_label}")
    lines.append(f"💠 4K Upscale: <b>{'✅ доступно' if has_4k else '❌ пока нет'}</b>")
    if post_id:
        lines.append(f"📣 Пост в AnimeHUB | Dream: <b>#{post_id}</b>")
    lines.extend(["", "⭐ Добавляй в избранное и отмечай прогресс кнопками ниже."])

    return "\n".join(lines)


def build_catalog_page(titles: list[dict], user_data: dict, page: int) -> tuple[str, InlineKeyboardMarkup]:
    available = [t for t in titles if has_access(user_data, t.get("min_access", "free"))]
    available.sort(key=lambda t: norm_title(t.get("name", "")))
    total = len(available)
    total_pages = max(1, (total + CATALOG_PAGE_SIZE - 1) // CATALOG_PAGE_SIZE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * CATALOG_PAGE_SIZE
    chunk = available[start:start + CATALOG_PAGE_SIZE]

    rows = []
    for t in chunk:
        quality = "💠" if t.get("has_4k") else "▫️"
        top = "🏆" if t.get("top150") else ""
        label = f"{quality}{top} {_short(t.get('name'), 44)}"
        rows.append([InlineKeyboardButton(label, callback_data=f"cat:{t['id']}")])

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"catpage:{page-1}"))
    nav.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="catnoop"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"catpage:{page+1}"))
    rows.append(nav)
    rows.append([InlineKeyboardButton("🔎 Поиск — /search название", callback_data="catnoop")])
    rows.append([InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")])

    four_k = sum(1 for t in available if t.get("has_4k"))
    text = (
        "📚 <b>Каталог AnimeHUB | Dream</b>\n\n"
        f"Тайтлов: <b>{total}</b> · с 4K: <b>{four_k}</b>\n"
        "💠 — есть 4K · ▫️ — 4K пока нет · 🏆 — входит в Top-150\n\n"
        "Нажми на тайтл, чтобы открыть его карточку."
    )
    return text, InlineKeyboardMarkup(rows)


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
    reply_markup = build_main_menu_keyboard(is_admin(data, update.effective_user.id))
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
        text, kb = build_catalog_page(titles, user_data, 1)
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
        if arg0.startswith(("friend_", "access_")):
            token = arg0
            invites = data.get("invites", {})
            hashed_key = invite_storage_key(token)
            # hashed_key — новый безопасный формат; token — поддержка старых ссылок до их истечения.
            storage_key = hashed_key if hashed_key in invites else token
            info = invites.get(storage_key)
            if info and info.get("type") in ("friend", "access"):
                if info.get("type") == "friend":
                    ensure_friend_access(user_data)
                else:
                    level = info.get("level", "friend")
                    if level in ACCESS_LEVELS and ACCESS_LEVELS[level] > ACCESS_LEVELS.get(user_data.get("access", "free"), 0):
                        user_data["access"] = level
                user_data["activated"] = True
                info["uses"] = info.get("uses", 0) + 1
                max_uses = info.get("max_uses")
                if max_uses is not None and info["uses"] >= max_uses:
                    invites.pop(storage_key, None)
                data["invites"] = invites
                await save_data(data)
                granted_level = user_data.get("access", "friend")
                text = (
                    "🎟 Приглашение активировано.\n\n"
                    f"Профиль активирован, уровень доступа: <b>{granted_level}</b>.\n\n"
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
            "• <code>/admin</code> – админ-панель\n"
            "• <code>/profile</code> – мой профиль\n"
            "• <code>/myid</code> – мой Telegram ID\n"
            "• <code>/title id</code> – карточка тайтла (или открой через каталог)\n"
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
            "• <code>/title id</code> – карточка тайтла (или открой через каталог)\n"
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
    known_filters = {"studio", "year", "status", "genre", "4k"}
    for token in tokens:
        if ":" in token:
            k, v = token.split(":", 1)
            k = k.strip().lower()
            v = v.strip()
            if k in known_filters and v:
                filters_out[k] = v
                continue
        qparts.append(token)
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
        aliases = " ".join(str(x) for x in t.get("aliases", []) if x).lower()
        post_id = str(t.get("channel_post_id") or "")
        studio = (t.get("studio") or "").lower()
        year = (t.get("year") or "").lower()
        status = (t.get("status") or "").lower()
        genres = (t.get("genres") or "").lower()

        ok = True
        if query:
            nq = norm_title(query)
            haystack = " ".join([norm_title(name), norm_title(tid), norm_title(aliases), post_id])
            if nq not in haystack:
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
        if ok and "4k" in flt:
            want_4k = flt["4k"].strip().lower() in {"1", "true", "yes", "да", "есть"}
            if bool(t.get("has_4k")) != want_4k:
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
        quality = "💠4K" if t.get("has_4k") else "▫️HD"
        post = f" · пост #{t.get('channel_post_id')}" if t.get("channel_post_id") else ""
        lines.append(f"• <b>{t['name']}</b>{extra} · {quality}{post} — <code>/title {t['id']}</code>")
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

    if check_rate_limit(uid, "suggest", 10.0):
        await update.effective_message.reply_text("Подожди немного перед следующим предложением.")
        return

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
    if len(text) > 2000:
        await update.effective_message.reply_text("Предложение слишком длинное. Максимум — 2000 символов.")
        return

    suggestions = data.setdefault("suggestions", {})
    numeric_ids = [int(x) for x in suggestions.keys() if str(x).isdigit()]
    sid = str((max(numeric_ids) + 1) if numeric_ids else 1)
    suggestions[sid] = {
        "user_id": uid,
        "username": user.username,
        "full_name": user.full_name,
        "text": text,
        "status": "new",
        "created_at": int(time.time()),
        "updated_at": int(time.time()),
    }
    data["suggestions"] = suggestions
    await save_data(data)

    admins_all = set(ADMINS) | set(data.get("admins", []))
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton(f"📩 Открыть предложение #{sid}", callback_data=f"adm:s:view:{sid}")]]
    )
    for aid in admins_all:
        try:
            await context.bot.send_message(
                chat_id=aid,
                text=(
                    f"📩 <b>Новое предложение #{sid}</b>\n\n"
                    f"От: <a href='tg://user?id={uid}'>{uid}</a>\n\n"
                    f"Текст:\n{html_escape(text)}"
                ),
                reply_markup=kb,
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            logger.exception("Не удалось уведомить администратора %s о предложении %s", aid, sid)

    await update.effective_message.reply_text(
        f"Спасибо! Предложение <b>#{sid}</b> сохранено и отправлено админам."
    )


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
    add_audit(data, user_id, "user_ban_command", str(target_id))
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
        add_audit(data, user_id, "user_unban_command", str(target_id))
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
    add_audit(data, user_id, "admin_add_command", str(target_id))
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
    add_audit(data, user_id, "admin_remove_command", str(target_id))
    await save_data(data)
    await update.effective_message.reply_text(f"Пользователь {target_id} убран из админов.")


# =========================
# ADMIN PANEL
# =========================

ADMIN_TITLE_PAGE_SIZE = 8
ADMIN_USER_PAGE_SIZE = 8
ADMIN_SUGGESTION_PAGE_SIZE = 8
ADMIN_POST_PAGE_SIZE = 8
ADMIN_AUDIT_LIMIT = 200

ADMIN_TITLE_FIELDS = {
    "name": "Название",
    "season": "Сезон / формат",
    "status": "Статус",
    "episodes": "Эпизоды",
    "year": "Год",
    "studio": "Студия",
    "author": "Автор",
    "director": "Режиссёр",
    "voice": "Озвучка",
    "shiki": "Shikimori",
    "imdb": "IMDb",
    "kp": "Кинопоиск",
    "genres": "Жанры",
    "playlist": "Плейлист",
    "desc": "Описание",
    "channel_post_id": "ID поста канала",
    "aliases": "Алиасы через |",
}

SUGGESTION_STATUS_LABELS = {
    "new": "🆕 Новое",
    "planned": "🕒 В планах",
    "done": "✅ Выполнено",
    "rejected": "❌ Отклонено",
}


def _admin_private_chat(update: Update) -> bool:
    return bool(update.effective_chat and update.effective_chat.type == "private")


def _fmt_time(ts: int | float | None) -> str:
    if not ts:
        return "—"
    try:
        return time.strftime("%d.%m.%Y %H:%M", time.localtime(float(ts)))
    except (ValueError, TypeError, OSError):
        return "—"


def _fmt_bytes(size: int) -> str:
    value = float(max(0, size))
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if value < 1024 or unit == "ГБ":
            return f"{value:.1f} {unit}" if unit != "Б" else f"{int(value)} {unit}"
        value /= 1024
    return f"{value:.1f} ГБ"


def _safe_file_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def _short(text: str | None, limit: int = 70) -> str:
    clean = " ".join((text or "").split())
    return clean if len(clean) <= limit else clean[: limit - 1] + "…"


def add_audit(data: dict, admin_id: int, action: str, target: str = "", details: str = "") -> None:
    log = data.setdefault("audit_log", [])
    log.append(
        {
            "ts": int(time.time()),
            "admin_id": admin_id,
            "action": action,
            "target": str(target or ""),
            "details": _short(str(details or ""), 160),
        }
    )
    if len(log) > ADMIN_AUDIT_LIMIT:
        del log[:-ADMIN_AUDIT_LIMIT]


async def _admin_render(update: Update, text: str, kb: InlineKeyboardMarkup | None = None) -> None:
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, reply_markup=kb)
            return
        except Exception:
            pass
    await update.effective_message.reply_text(text, reply_markup=kb)


def _admin_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📊 Дашборд", callback_data="adm:dash")],
            [
                InlineKeyboardButton("🎬 Тайтлы", callback_data="adm:t:list:1"),
                InlineKeyboardButton("📝 Посты", callback_data="adm:p:list:1"),
            ],
            [
                InlineKeyboardButton("👥 Пользователи", callback_data="adm:u:list:1"),
                InlineKeyboardButton("📩 Предложения", callback_data="adm:s:list:1"),
            ],
            [
                InlineKeyboardButton("📢 Рассылка", callback_data="adm:broadcast:start"),
                InlineKeyboardButton("🔐 Доступы", callback_data="adm:access"),
            ],
            [
                InlineKeyboardButton("🧰 Система", callback_data="adm:system"),
                InlineKeyboardButton("📜 Журнал", callback_data="adm:audit"),
            ],
            [InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")],
        ]
    )


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await load_data()
    if not is_admin(data, update.effective_user.id):
        await update.effective_message.reply_text("Эта команда доступна только администраторам.")
        return
    if not _admin_private_chat(update):
        await update.effective_message.reply_text("Админ-панель доступна только в личном чате с ботом.")
        return
    context.user_data.pop("admin_pending", None)
    await show_admin_home(update, context, data)


async def merged_channel_posts(data: dict) -> dict:
    """Реестр постов: объединяет исторические ссылки каталога и посты, созданные ботом."""
    registry = {str(mid): dict(info) for mid, info in data.get("posts", {}).items() if isinstance(info, dict)}
    for title in await load_titles():
        post_id = title.get("channel_post_id")
        try:
            mid = str(int(post_id))
        except (TypeError, ValueError):
            continue
        info = registry.setdefault(mid, {})
        info.setdefault("title_id", title.get("id"))
        info.setdefault("created_at", 0)
        info.setdefault("caption", None)
        info["known_catalog_post"] = True
    return registry


async def show_admin_home(update: Update, context: ContextTypes.DEFAULT_TYPE, data: dict) -> None:
    users = data.get("users", {})
    activated = sum(1 for u in users.values() if u.get("activated"))
    new_suggestions = sum(
        1 for item in data.get("suggestions", {}).values() if item.get("status", "new") == "new"
    )
    titles = await load_titles()
    merged_posts = await merged_channel_posts(data)
    text = (
        "🛠 <b>AnimeHUB | Dream — Админ-панель</b>\n\n"
        f"👥 Активных пользователей: <b>{activated}</b>\n"
        f"🎬 Тайтлов в каталоге: <b>{len(titles)}</b>\n"
        f"📝 Постов в реестре: <b>{len(merged_posts)}</b>\n"
        f"📩 Новых предложений: <b>{new_suggestions}</b>\n\n"
        "Здесь собраны основные операции по каналу и боту."
    )
    await _admin_render(update, text, _admin_home_keyboard())


async def show_admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE, data: dict) -> None:
    users = data.get("users", {})
    titles = await load_titles()
    total_users = len(users)
    activated = sum(1 for u in users.values() if u.get("activated"))
    friends = sum(1 for u in users.values() if u.get("access") == "friend")
    vips = sum(1 for u in users.values() if u.get("access") == "vip")
    banned = sum(1 for v in data.get("banned", {}).values() if v)
    hot = sum(1 for t in titles if t.get("hot"))
    top150 = sum(1 for t in titles if t.get("top150"))
    four_k = sum(1 for t in titles if t.get("has_4k"))
    suggestions = data.get("suggestions", {})
    new_suggestions = sum(1 for x in suggestions.values() if x.get("status", "new") == "new")
    stats = data.get("stats", {})
    merged_posts = await merged_channel_posts(data)
    sections = stats.get("sections", {})
    top_sections = sorted(sections.items(), key=lambda x: x[1], reverse=True)[:4]
    section_text = "\n".join(f"• {html_escape(str(k))}: <b>{v}</b>" for k, v in top_sections) or "• пока нет данных"
    uptime = max(0, int(time.time() - BOT_STARTED_AT))
    hours, rem = divmod(uptime, 3600)
    minutes = rem // 60
    text = (
        "📊 <b>Дашборд</b>\n\n"
        f"👥 Пользователи: <b>{total_users}</b> · активированы <b>{activated}</b>\n"
        f"🤝 Friend: <b>{friends}</b> · 💎 VIP: <b>{vips}</b> · 🚫 бан: <b>{banned}</b>\n\n"
        f"🎬 Тайтлы: <b>{len(titles)}</b> · 💠 4K: <b>{four_k}</b> · 🔥 hot: <b>{hot}</b> · 🏆 Top-150: <b>{top150}</b>\n"
        f"📝 Посты: <b>{len(merged_posts)}</b> · создано ботом: <b>{stats.get('posts_created', 0)}</b>\n"
        f"📩 Предложения: <b>{len(suggestions)}</b> · новых: <b>{new_suggestions}</b>\n"
        f"📢 Рассылок: <b>{stats.get('broadcasts_sent', 0)}</b> · доставок: <b>{stats.get('broadcast_recipients', 0)}</b>\n\n"
        "📈 <b>Популярные разделы</b>\n"
        f"{section_text}\n\n"
        f"⏱ Аптайм процесса: <b>{hours}ч {minutes}м</b>"
    )
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔄 Обновить", callback_data="adm:dash")],
            [InlineKeyboardButton("⬅️ Админ-панель", callback_data="adm:home")],
        ]
    )
    await _admin_render(update, text, kb)


def _title_admin_label(t: dict) -> str:
    hot = "🔥 " if t.get("hot") else ""
    access = {"free": "🟢", "friend": "🟡", "vip": "💎"}.get(t.get("min_access", "free"), "⚪")
    return f"{hot}{access} {_short(t.get('name'), 34)}"


async def show_admin_titles(update: Update, context: ContextTypes.DEFAULT_TYPE, data: dict, page: int = 1) -> None:
    titles = sorted(await load_titles(), key=lambda t: (t.get("name") or "").lower())
    total_pages = max(1, (len(titles) + ADMIN_TITLE_PAGE_SIZE - 1) // ADMIN_TITLE_PAGE_SIZE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * ADMIN_TITLE_PAGE_SIZE
    chunk = titles[start : start + ADMIN_TITLE_PAGE_SIZE]
    kb = []
    for t in chunk:
        kb.append([InlineKeyboardButton(_title_admin_label(t), callback_data=f"adm:t:view:{t['id']}")])
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"adm:t:list:{page-1}"))
    nav.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="adm:t:noop"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"adm:t:list:{page+1}"))
    kb.append(nav)
    kb.extend(
        [
            [
                InlineKeyboardButton("➕ Добавить", callback_data="adm:t:add"),
                InlineKeyboardButton("🔎 Найти", callback_data="adm:t:search"),
            ],
            [InlineKeyboardButton("⬅️ Админ-панель", callback_data="adm:home")],
        ]
    )
    text = (
        "🎬 <b>Управление тайтлами</b>\n\n"
        f"Всего: <b>{len(titles)}</b>\n"
        "🟢 free · 🟡 friend · 💎 VIP · 🔥 популярное\n\n"
        "Выбери тайтл для редактирования."
    )
    await _admin_render(update, text, InlineKeyboardMarkup(kb))


async def show_admin_title_card(update: Update, context: ContextTypes.DEFAULT_TYPE, data: dict, tid: str) -> None:
    await load_titles()
    t = TITLES_BY_ID.get(tid)
    if not t:
        await _admin_render(update, "Тайтл не найден.", InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ К тайтлам", callback_data="adm:t:list:1")]]))
        return
    access = t.get("min_access", "free")
    post_id = t.get("channel_post_id") or "—"
    text = (
        f"🎬 <b>{html_escape(str(t.get('name', tid)))}</b>\n"
        f"<code>{html_escape(tid)}</code>\n\n"
        f"📅 {html_escape(str(t.get('year', '—')))} · 🎞 {html_escape(str(t.get('episodes', '—')))}\n"
        f"📌 {html_escape(str(t.get('status', '—')))}\n"
        f"🏢 {html_escape(str(t.get('studio', '—')))}\n"
        f"📣 Пост: <b>#{html_escape(str(post_id))}</b>\n"
        f"💠 4K: <b>{'есть' if t.get('has_4k') else 'нет'}</b>\n"
        f"🔑 Доступ: <b>{html_escape(access)}</b>\n"
        f"🔥 Популярное: <b>{'да' if t.get('hot') else 'нет'}</b>\n"
        f"🏆 Top-150: <b>{'да' if t.get('top150') else 'нет'}</b>\n\n"
        f"🏷 {_short(t.get('genres'), 100)}"
    )
    rows = [
        [
            InlineKeyboardButton("🔥 Вкл/выкл Hot", callback_data=f"adm:t:hot:{tid}"),
            InlineKeyboardButton("💠 Вкл/выкл 4K", callback_data=f"adm:t:4k:{tid}"),
        ],
        [InlineKeyboardButton("🔑 Сменить доступ", callback_data=f"adm:t:access:{tid}")],
        [InlineKeyboardButton("✏️ Редактировать поля", callback_data=f"adm:t:fields:{tid}")],
        [InlineKeyboardButton("👁 Предпросмотр карточки", callback_data=f"adm:t:preview:{tid}")],
    ]
    url = title_channel_url(t)
    if url:
        rows.append([InlineKeyboardButton("📣 Открыть пост в канале", url=url)])
    rows.extend(
        [
            [InlineKeyboardButton("🗑 Удалить тайтл", callback_data=f"adm:t:delete:{tid}")],
            [InlineKeyboardButton("⬅️ К тайтлам", callback_data="adm:t:list:1")],
        ]
    )
    await _admin_render(update, text, InlineKeyboardMarkup(rows))


async def show_admin_title_fields(update: Update, context: ContextTypes.DEFAULT_TYPE, data: dict, tid: str) -> None:
    await load_titles()
    if tid not in TITLES_BY_ID:
        await show_admin_titles(update, context, data, 1)
        return
    rows = []
    items = list(ADMIN_TITLE_FIELDS.items())
    for i in range(0, len(items), 2):
        row = []
        for key, label in items[i : i + 2]:
            row.append(InlineKeyboardButton(label, callback_data=f"adm:t:field:{tid}:{key}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("⬅️ К тайтлу", callback_data=f"adm:t:view:{tid}")])
    await _admin_render(
        update,
        "✏️ <b>Редактирование тайтла</b>\n\nВыбери поле, затем отправь новое значение одним сообщением.",
        InlineKeyboardMarkup(rows),
    )


async def _admin_title_search_results(update: Update, query_text: str) -> None:
    titles = await load_titles()
    nq = norm_title(query_text)
    results = [t for t in titles if nq in norm_title(t.get("name", "")) or nq in norm_title(t.get("id", ""))][:20]
    if not results:
        await update.effective_message.reply_text("По запросу ничего не найдено.")
        return
    kb = [[InlineKeyboardButton(_title_admin_label(t), callback_data=f"adm:t:view:{t['id']}")] for t in results]
    kb.append([InlineKeyboardButton("⬅️ К тайтлам", callback_data="adm:t:list:1")])
    await update.effective_message.reply_text(
        f"🔎 Найдено: <b>{len(results)}</b>", reply_markup=InlineKeyboardMarkup(kb)
    )


def _user_display(uid: str, u: dict) -> str:
    name = u.get("full_name") or ("@" + u.get("username") if u.get("username") else f"ID {uid}")
    access = {"free": "🟢", "friend": "🟡", "vip": "💎"}.get(u.get("access", "free"), "⚪")
    return f"{access} {_short(name, 34)}"


async def show_admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE, data: dict, page: int = 1) -> None:
    users = list(data.get("users", {}).items())
    users.sort(key=lambda item: item[1].get("created_at", 0), reverse=True)
    total_pages = max(1, (len(users) + ADMIN_USER_PAGE_SIZE - 1) // ADMIN_USER_PAGE_SIZE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * ADMIN_USER_PAGE_SIZE
    chunk = users[start : start + ADMIN_USER_PAGE_SIZE]
    kb = [[InlineKeyboardButton(_user_display(uid, u), callback_data=f"adm:u:view:{uid}")] for uid, u in chunk]
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"adm:u:list:{page-1}"))
    nav.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="adm:u:noop"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"adm:u:list:{page+1}"))
    kb.append(nav)
    kb.extend(
        [
            [InlineKeyboardButton("🔎 Найти пользователя", callback_data="adm:u:search")],
            [InlineKeyboardButton("⬅️ Админ-панель", callback_data="adm:home")],
        ]
    )
    await _admin_render(
        update,
        f"👥 <b>Пользователи</b>\n\nВсего записей: <b>{len(users)}</b>\nПоследние зарегистрированные — сверху.",
        InlineKeyboardMarkup(kb),
    )


async def show_admin_user_card(update: Update, context: ContextTypes.DEFAULT_TYPE, data: dict, uid: str) -> None:
    u = data.get("users", {}).get(str(uid))
    if not u:
        await _admin_render(update, "Пользователь не найден в базе.", InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ К пользователям", callback_data="adm:u:list:1")]]))
        return
    banned = bool(data.get("banned", {}).get(str(uid)))
    admin_status = is_admin(data, int(uid))
    name = html_escape(u.get("full_name") or "—")
    username = html_escape("@" + u["username"] if u.get("username") else "—")
    text = (
        f"👤 <b>{name}</b>\n"
        f"{username}\n"
        f"ID: <code>{uid}</code>\n\n"
        f"🔑 Доступ: <b>{html_escape(u.get('access', 'free'))}</b>\n"
        f"⚡ Активирован: <b>{'да' if u.get('activated') else 'нет'}</b>\n"
        f"🚫 Заблокирован: <b>{'да' if banned else 'нет'}</b>\n"
        f"🛡 Администратор: <b>{'да' if admin_status else 'нет'}</b>\n\n"
        f"⭐ Избранное: <b>{len(u.get('favorites', []))}</b>\n"
        f"🏆 Top-150 просмотрено: <b>{len(u.get('watched_150', []))}</b>\n"
        f"🤝 Друзья: <b>{len(u.get('friends', []))}</b>\n"
        f"📅 В базе с: <b>{_fmt_time(u.get('created_at'))}</b>"
    )
    rows = [
        [
            InlineKeyboardButton("🟢 free", callback_data=f"adm:u:access:{uid}:free"),
            InlineKeyboardButton("🟡 friend", callback_data=f"adm:u:access:{uid}:friend"),
            InlineKeyboardButton("💎 VIP", callback_data=f"adm:u:access:{uid}:vip"),
        ],
        [InlineKeyboardButton("✉️ Написать пользователю", callback_data=f"adm:u:message:{uid}")],
    ]
    if banned:
        rows.append([InlineKeyboardButton("✅ Разбанить", callback_data=f"adm:u:unban:{uid}")])
    else:
        rows.append([InlineKeyboardButton("🚫 Заблокировать", callback_data=f"adm:u:ban:{uid}")])
    if is_root_admin(update.effective_user.id) and not is_root_admin(int(uid)):
        if admin_status:
            rows.append([InlineKeyboardButton("➖ Снять администратора", callback_data=f"adm:u:demote:{uid}")])
        else:
            rows.append([InlineKeyboardButton("➕ Сделать администратором", callback_data=f"adm:u:promote:{uid}")])
    rows.append([InlineKeyboardButton("⬅️ К пользователям", callback_data="adm:u:list:1")])
    await _admin_render(update, text, InlineKeyboardMarkup(rows))


async def _admin_user_search_results(update: Update, data: dict, query_text: str) -> None:
    q = query_text.strip().lower().lstrip("@")
    results = []
    for uid, u in data.get("users", {}).items():
        if q == uid or q in (u.get("username") or "").lower() or q in (u.get("full_name") or "").lower():
            results.append((uid, u))
        if len(results) >= 20:
            break
    if not results:
        await update.effective_message.reply_text("Пользователь не найден в локальной базе бота.")
        return
    kb = [[InlineKeyboardButton(_user_display(uid, u), callback_data=f"adm:u:view:{uid}")] for uid, u in results]
    kb.append([InlineKeyboardButton("⬅️ К пользователям", callback_data="adm:u:list:1")])
    await update.effective_message.reply_text(
        f"🔎 Найдено: <b>{len(results)}</b>", reply_markup=InlineKeyboardMarkup(kb)
    )


async def show_admin_suggestions(update: Update, context: ContextTypes.DEFAULT_TYPE, data: dict, page: int = 1) -> None:
    items = list(data.get("suggestions", {}).items())
    priority = {"new": 0, "planned": 1, "done": 2, "rejected": 3}
    items.sort(key=lambda x: (priority.get(x[1].get("status", "new"), 9), -x[1].get("created_at", 0)))
    total_pages = max(1, (len(items) + ADMIN_SUGGESTION_PAGE_SIZE - 1) // ADMIN_SUGGESTION_PAGE_SIZE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * ADMIN_SUGGESTION_PAGE_SIZE
    chunk = items[start : start + ADMIN_SUGGESTION_PAGE_SIZE]
    kb = []
    for sid, item in chunk:
        status = SUGGESTION_STATUS_LABELS.get(item.get("status", "new"), "•")
        kb.append([InlineKeyboardButton(f"{status} #{sid} · {_short(item.get('text'), 28)}", callback_data=f"adm:s:view:{sid}")])
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"adm:s:list:{page-1}"))
    nav.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="adm:s:noop"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"adm:s:list:{page+1}"))
    kb.append(nav)
    kb.append([InlineKeyboardButton("⬅️ Админ-панель", callback_data="adm:home")])
    new_count = sum(1 for _, x in items if x.get("status", "new") == "new")
    await _admin_render(
        update,
        f"📩 <b>Предложения</b>\n\nВсего: <b>{len(items)}</b> · новых: <b>{new_count}</b>",
        InlineKeyboardMarkup(kb),
    )


async def show_admin_suggestion_card(update: Update, context: ContextTypes.DEFAULT_TYPE, data: dict, sid: str) -> None:
    item = data.get("suggestions", {}).get(str(sid))
    if not item:
        await show_admin_suggestions(update, context, data, 1)
        return
    uid = item.get("user_id")
    status = SUGGESTION_STATUS_LABELS.get(item.get("status", "new"), item.get("status", "new"))
    text = (
        f"📩 <b>Предложение #{sid}</b>\n\n"
        f"Статус: <b>{status}</b>\n"
        f"От: <a href='tg://user?id={uid}'>{uid}</a>\n"
        f"Создано: <b>{_fmt_time(item.get('created_at'))}</b>\n\n"
        f"{html_escape(item.get('text', ''))}"
    )
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🕒 В планы", callback_data=f"adm:s:set:{sid}:planned"),
                InlineKeyboardButton("✅ Выполнено", callback_data=f"adm:s:set:{sid}:done"),
            ],
            [
                InlineKeyboardButton("🆕 Вернуть в новые", callback_data=f"adm:s:set:{sid}:new"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"adm:s:set:{sid}:rejected"),
            ],
            [InlineKeyboardButton("🗑 Удалить запись", callback_data=f"adm:s:delete:{sid}")],
            [InlineKeyboardButton("⬅️ К предложениям", callback_data="adm:s:list:1")],
        ]
    )
    await _admin_render(update, text, kb)


async def show_admin_posts(update: Update, context: ContextTypes.DEFAULT_TYPE, data: dict, page: int = 1) -> None:
    posts = list((await merged_channel_posts(data)).items())
    posts.sort(key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0, reverse=True)
    total_pages = max(1, (len(posts) + ADMIN_POST_PAGE_SIZE - 1) // ADMIN_POST_PAGE_SIZE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * ADMIN_POST_PAGE_SIZE
    chunk = posts[start : start + ADMIN_POST_PAGE_SIZE]
    kb = []
    for mid, info in chunk:
        title_id = info.get("title_id") or "без тайтла"
        kb.append([InlineKeyboardButton(f"#{mid} · {_short(title_id, 28)}", callback_data=f"adm:p:view:{mid}")])
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"adm:p:list:{page-1}"))
    nav.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="adm:p:noop"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"adm:p:list:{page+1}"))
    kb.append(nav)
    kb.extend(
        [
            [InlineKeyboardButton("➕ Создать через предпросмотр", callback_data="adm:post:new_draft")],
            [InlineKeyboardButton("⚡ Опубликовать сразу", callback_data="adm:post:new_direct")],
            [InlineKeyboardButton("⬅️ Админ-панель", callback_data="adm:home")],
        ]
    )
    await _admin_render(
        update,
        f"📝 <b>Посты канала</b>\n\nВ реестре бота: <b>{len(posts)}</b>\nДля обычной работы безопаснее использовать предпросмотр.",
        InlineKeyboardMarkup(kb),
    )


async def show_admin_post_card(update: Update, context: ContextTypes.DEFAULT_TYPE, data: dict, mid: str) -> None:
    info = (await merged_channel_posts(data)).get(str(mid))
    if not info:
        await show_admin_posts(update, context, data, 1)
        return
    channel = CHANNEL_USERNAME.lstrip("@")
    link = f"https://t.me/{channel}/{mid}"
    caption = html_escape(_short(info.get("caption"), 500) or "—")
    text = (
        f"📝 <b>Пост #{mid}</b>\n\n"
        f"🎬 Тайтл: <code>{html_escape(str(info.get('title_id') or 'не привязан'))}</code>\n"
        f"📅 Создан: <b>{_fmt_time(info.get('created_at'))}</b>\n\n"
        f"{caption}"
    )
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔗 Открыть в канале", url=link)],
            [
                InlineKeyboardButton("✏️ Редактировать", callback_data=f"adm:post:edit:{mid}"),
                InlineKeyboardButton("♻️ Репост", callback_data=f"adm:p:repost:{mid}"),
            ],
            [InlineKeyboardButton("🔗 Привязать тайтл", callback_data=f"adm:p:link:{mid}")],
            [InlineKeyboardButton("🗑 Удалить из канала", callback_data=f"adm:p:delete:{mid}")],
            [InlineKeyboardButton("⬅️ К постам", callback_data="adm:p:list:1")],
        ]
    )
    await _admin_render(update, text, kb)


async def show_admin_access(update: Update, context: ContextTypes.DEFAULT_TYPE, data: dict) -> None:
    all_admins = sorted(set(ADMINS) | set(data.get("admins", [])))
    admin_lines = []
    for aid in all_admins:
        admin_lines.append(f"• <code>{aid}</code>{' · root' if aid in ADMINS else ''}")
    text = (
        "🔐 <b>Доступы и администраторы</b>\n\n"
        f"💎 ACCESS_CODE_VIP: <b>{'настроен' if os.getenv('ACCESS_CODE_VIP', '').strip() else 'не задан'}</b>\n"
        f"🤝 ACCESS_CODE_FRIEND: <b>{'настроен' if os.getenv('ACCESS_CODE_FRIEND', '').strip() else 'не задан'}</b>\n\n"
        "🛡 <b>Администраторы</b>\n"
        + ("\n".join(admin_lines) if admin_lines else "—")
        + "\n\nЗначения секретных кодов панель намеренно не показывает."
    )
    rows = [
        [
            InlineKeyboardButton("🎟 Friend-приглашение", callback_data="adm:invite:friend"),
            InlineKeyboardButton("💎 VIP-приглашение", callback_data="adm:invite:vip"),
        ],
    ]
    if is_root_admin(update.effective_user.id):
        rows.append([InlineKeyboardButton("➕ Добавить админа по ID", callback_data="adm:admin:add")])
    rows.append([InlineKeyboardButton("⬅️ Админ-панель", callback_data="adm:home")])
    await _admin_render(update, text, InlineKeyboardMarkup(rows))


async def show_admin_system(update: Update, context: ContextTypes.DEFAULT_TYPE, data: dict) -> None:
    try:
        bot_member = await context.bot.get_chat_member(CHANNEL_USERNAME, context.bot.id)
        channel_status = bot_member.status
    except Exception:
        channel_status = "не удалось проверить"
    storage_dir = os.path.dirname(os.path.abspath(DATA_FILE)) or "."
    try:
        usage = shutil.disk_usage(storage_dir)
        disk_text = f"{_fmt_bytes(usage.free)} свободно из {_fmt_bytes(usage.total)}"
    except OSError:
        disk_text = "не удалось определить"
    text = (
        "🧰 <b>Система</b>\n\n"
        f"🤖 Бот: <b>@{html_escape(context.bot.username or '—')}</b>\n"
        f"📣 Канал: <b>{html_escape(CHANNEL_USERNAME)}</b>\n"
        f"🛡 Статус бота в канале: <b>{html_escape(str(channel_status))}</b>\n\n"
        f"📁 Папка данных: <code>{html_escape(storage_dir)}</code>\n"
        f"🗃 bot_data.json: <b>{_fmt_bytes(_safe_file_size(DATA_FILE))}</b>\n"
        f"🎬 titles.json: <b>{_fmt_bytes(_safe_file_size(TITLES_FILE))}</b>\n"
        f"💾 Диск: <b>{disk_text}</b>\n\n"
        f"🔐 BOT_TOKEN: <b>{'задан' if BOT_TOKEN else 'не задан'}</b>\n"
        f"🧹 Drop pending updates: <b>{DROP_PENDING_UPDATES}</b>"
    )
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💾 Сделать резервную копию", callback_data="adm:system:backup")],
            [InlineKeyboardButton("🔄 Обновить статус", callback_data="adm:system")],
            [InlineKeyboardButton("⬅️ Админ-панель", callback_data="adm:home")],
        ]
    )
    await _admin_render(update, text, kb)


async def show_admin_audit(update: Update, context: ContextTypes.DEFAULT_TYPE, data: dict) -> None:
    log = list(reversed(data.get("audit_log", [])[-20:]))
    lines = ["📜 <b>Последние действия администраторов</b>", ""]
    if not log:
        lines.append("Журнал пока пуст.")
    else:
        for item in log:
            action = html_escape(str(item.get("action", "—")))
            target = html_escape(str(item.get("target", "")))
            details = html_escape(str(item.get("details", "")))
            suffix = f" · {target}" if target else ""
            if details:
                suffix += f" · {_short(details, 70)}"
            lines.append(f"• {_fmt_time(item.get('ts'))} · <code>{item.get('admin_id')}</code> · <b>{action}</b>{suffix}")
    rows = [[InlineKeyboardButton("🔄 Обновить", callback_data="adm:audit")]]
    if is_root_admin(update.effective_user.id) and data.get("audit_log"):
        rows.append([InlineKeyboardButton("🧹 Очистить журнал", callback_data="adm:audit:clear_confirm")])
    rows.append([InlineKeyboardButton("⬅️ Админ-панель", callback_data="adm:home")])
    await _admin_render(update, "\n".join(lines), InlineKeyboardMarkup(rows))


async def admin_post_start_draft_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    return await post_start_common(update, context, mode="draft")


async def admin_post_start_direct_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    return await post_start_common(update, context, mode="channel")


async def admin_edit_post_start_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    data = await load_data()
    if not is_admin(data, update.effective_user.id):
        await update.effective_message.reply_text("Эта операция доступна только администратору.")
        return ConversationHandler.END
    try:
        msg_id = int(update.callback_query.data.rsplit(":", 1)[1])
    except (ValueError, IndexError):
        return ConversationHandler.END
    context.user_data["edit_msg_id"] = msg_id
    await update.effective_message.reply_text(
        f"Редактирование поста <code>#{msg_id}</code>.\n\n"
        "Шаг 1/4. Отправь новую обложку как фото или <code>-</code>, если обложку менять не нужно.\n"
        "Для отмены: <code>/cancel</code>."
    )
    return EDIT_PHOTO


async def handle_admin_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pending = context.user_data.get("admin_pending")
    if not pending:
        return
    data = await load_data()
    admin_id = update.effective_user.id
    if not is_admin(data, admin_id) or not _admin_private_chat(update):
        context.user_data.pop("admin_pending", None)
        return
    text = (update.effective_message.text or "").strip()
    action = pending.get("action")
    context.user_data.pop("admin_pending", None)

    if action == "title_search":
        await _admin_title_search_results(update, text)
        return

    if action == "title_add":
        if "|" not in text:
            await update.effective_message.reply_text("Нужен формат: <code>Название | id</code>. Попробуй ещё раз через админ-панель.")
            return
        name, tid = [x.strip() for x in text.split("|", 1)]
        tid = tid.lower()
        if not name or not re.fullmatch(r"[a-z0-9_-]{2,32}", tid):
            await update.effective_message.reply_text("ID должен состоять из a-z, 0-9, _ или - и быть длиной 2–32 символа.")
            return
        titles = await load_titles()
        if tid in TITLES_BY_ID:
            await update.effective_message.reply_text("Такой ID уже существует.")
            return
        title = {
            "id": tid,
            "name": name,
            "season": "Сезон 1",
            "status": "Вышел",
            "episodes": "?",
            "year": "----",
            "studio": "-",
            "author": "-",
            "director": "-",
            "voice": "-",
            "shiki": "-",
            "imdb": "-",
            "kp": "-",
            "genres": "-",
            "playlist": "-",
            "desc": "-",
            "min_access": "free",
            "hot": False,
            "has_4k": False,
            "channel_post_id": None,
            "aliases": [],
            "added_at": int(time.time()),
        }
        titles.append(title)
        await save_titles(titles)
        add_audit(data, admin_id, "title_add", tid, name)
        await save_data(data)
        await update.effective_message.reply_text(
            f"✅ Тайтл <b>{html_escape(name)}</b> создан. Теперь заполни его поля.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✏️ Открыть тайтл", callback_data=f"adm:t:view:{tid}")]]),
        )
        return

    if action == "title_edit":
        tid = pending.get("title_id")
        field = pending.get("field")
        if field not in ADMIN_TITLE_FIELDS:
            return
        titles = await load_titles()
        target = next((t for t in titles if t.get("id") == tid), None)
        if not target:
            await update.effective_message.reply_text("Тайтл больше не найден.")
            return
        value = "-" if text == "-" else text
        if len(value) > (2200 if field == "desc" else 700):
            await update.effective_message.reply_text("Значение слишком длинное.")
            return
        if field == "channel_post_id":
            if value == "-":
                target[field] = None
            else:
                try:
                    target[field] = int(value)
                    target["channel_post_deleted"] = False
                except ValueError:
                    await update.effective_message.reply_text("ID поста должен быть числом.")
                    return
        elif field == "aliases":
            target[field] = [x.strip() for x in value.split("|") if x.strip()] if value != "-" else []
        else:
            target[field] = value
        await save_titles(titles)
        add_audit(data, admin_id, "title_edit", tid, ADMIN_TITLE_FIELDS[field])
        await save_data(data)
        await update.effective_message.reply_text(
            "✅ Поле обновлено.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ К тайтлу", callback_data=f"adm:t:view:{tid}")]]),
        )
        return

    if action == "user_search":
        await _admin_user_search_results(update, data, text)
        return

    if action == "user_message":
        uid = int(pending.get("user_id"))
        try:
            await context.bot.send_message(chat_id=uid, text=text, parse_mode=None)
            add_audit(data, admin_id, "user_message", str(uid), _short(text, 80))
            await save_data(data)
            await update.effective_message.reply_text("✅ Сообщение отправлено пользователю.")
        except Exception:
            logger.exception("Не удалось отправить сообщение пользователю %s", uid)
            await update.effective_message.reply_text("Не удалось отправить сообщение. Возможно, пользователь заблокировал бота.")
        return

    if action == "post_link":
        mid = str(pending.get("message_id"))
        tid = text.lower()
        await load_titles()
        if tid not in TITLES_BY_ID:
            await update.effective_message.reply_text("Тайтл с таким ID не найден.")
            return
        info = data.setdefault("posts", {}).setdefault(mid, {})
        info["title_id"] = tid
        info.setdefault("created_at", int(time.time()))
        info.setdefault("caption", None)
        add_audit(data, admin_id, "post_link", mid, tid)
        await save_data(data)
        await update.effective_message.reply_text(
            "✅ Пост привязан к тайтлу.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ К посту", callback_data=f"adm:p:view:{mid}")]]),
        )
        return

    if action == "broadcast":
        if len(text) > 4000:
            await update.effective_message.reply_text("Рассылка слишком длинная. Максимум — 4000 символов.")
            return
        context.user_data["admin_broadcast_text"] = text
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ Отправить всем активированным", callback_data="adm:broadcast:confirm")],
                [InlineKeyboardButton("❌ Отмена", callback_data="adm:broadcast:cancel")],
            ]
        )
        await update.effective_message.reply_text(
            "📢 Предпросмотр рассылки:\n\n" + text,
            reply_markup=kb,
            parse_mode=None,
        )
        return

    if action == "admin_add":
        if not is_root_admin(admin_id):
            return
        try:
            uid = int(text)
        except ValueError:
            await update.effective_message.reply_text("Telegram ID должен быть числом.")
            return
        admins = data.setdefault("admins", [])
        if uid not in admins and uid not in ADMINS:
            admins.append(uid)
            add_audit(data, admin_id, "admin_add", str(uid))
            await save_data(data)
        await update.effective_message.reply_text("✅ Администратор добавлен.")
        return


async def _create_admin_access_invite(update: Update, context: ContextTypes.DEFAULT_TYPE, data: dict, level: str) -> None:
    token = f"access_{secrets.token_urlsafe(24)}"
    key = invite_storage_key(token)
    data.setdefault("invites", {})[key] = {
        "type": "access",
        "level": level,
        "created_by": update.effective_user.id,
        "created_at": int(time.time()),
        "uses": 0,
        "max_uses": 1,
    }
    add_audit(data, update.effective_user.id, "invite_create", level, "1 use")
    await save_data(data)
    link = f"https://t.me/{context.bot.username}?start={token}"
    await update.effective_message.reply_text(
        f"🎟 Одноразовое приглашение уровня <b>{level}</b>:\n<code>{link}</code>"
    )


async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, data: dict, data_str: str) -> None:
    admin_id = update.effective_user.id
    if not is_admin(data, admin_id):
        await update.effective_message.reply_text("Нет доступа к админ-панели.")
        return
    if not _admin_private_chat(update):
        await update.effective_message.reply_text("Админ-панель работает только в личном чате.")
        return

    if data_str in {"adm:t:noop", "adm:u:noop", "adm:s:noop", "adm:p:noop"}:
        return

    if data_str == "adm:home":
        context.user_data.pop("admin_pending", None)
        await show_admin_home(update, context, data)
        return
    if data_str == "adm:dash":
        await show_admin_dashboard(update, context, data)
        return

    if data_str.startswith("adm:t:list:"):
        await show_admin_titles(update, context, data, int(data_str.rsplit(":", 1)[1]))
        return
    if data_str == "adm:t:add":
        context.user_data["admin_pending"] = {"action": "title_add"}
        await update.effective_message.reply_text(
            "➕ Отправь одной строкой:\n<code>Название тайтла | id_taitla</code>\n\n"
            "Например: <code>Монолог фармацевта | kusuriya_no_hitorigoto</code>"
        )
        return
    if data_str == "adm:t:search":
        context.user_data["admin_pending"] = {"action": "title_search"}
        await update.effective_message.reply_text("🔎 Отправь название или ID тайтла.")
        return
    if data_str.startswith("adm:t:view:"):
        await show_admin_title_card(update, context, data, data_str.split(":", 3)[3])
        return
    if data_str.startswith("adm:t:fields:"):
        await show_admin_title_fields(update, context, data, data_str.split(":", 3)[3])
        return
    if data_str.startswith("adm:t:field:"):
        _, _, _, tid, field = data_str.split(":", 4)
        if field not in ADMIN_TITLE_FIELDS:
            return
        context.user_data["admin_pending"] = {"action": "title_edit", "title_id": tid, "field": field}
        await update.effective_message.reply_text(
            f"✏️ Новое значение для <b>{ADMIN_TITLE_FIELDS[field]}</b>:\n"
            "Отправь текст одним сообщением. <code>-</code> — оставить прочерк."
        )
        return
    if data_str.startswith("adm:t:hot:"):
        tid = data_str.split(":", 3)[3]
        titles = await load_titles()
        t = next((x for x in titles if x.get("id") == tid), None)
        if t:
            t["hot"] = not bool(t.get("hot"))
            await save_titles(titles)
            add_audit(data, admin_id, "title_hot", tid, str(t["hot"]))
            await save_data(data)
        await show_admin_title_card(update, context, data, tid)
        return
    if data_str.startswith("adm:t:4k:"):
        tid = data_str.split(":", 3)[3]
        titles = await load_titles()
        t = next((x for x in titles if x.get("id") == tid), None)
        if t:
            t["has_4k"] = not bool(t.get("has_4k"))
            await save_titles(titles)
            add_audit(data, admin_id, "title_4k", tid, str(t["has_4k"]))
            await save_data(data)
        await show_admin_title_card(update, context, data, tid)
        return

    if data_str.startswith("adm:t:access:"):
        tid = data_str.split(":", 3)[3]
        titles = await load_titles()
        t = next((x for x in titles if x.get("id") == tid), None)
        if t:
            levels = ["free", "friend", "vip"]
            current = t.get("min_access", "free")
            t["min_access"] = levels[(levels.index(current) + 1) % len(levels)] if current in levels else "free"
            await save_titles(titles)
            add_audit(data, admin_id, "title_access", tid, t["min_access"])
            await save_data(data)
        await show_admin_title_card(update, context, data, tid)
        return
    if data_str.startswith("adm:t:preview:"):
        tid = data_str.split(":", 3)[3]
        await load_titles()
        t = TITLES_BY_ID.get(tid)
        if t:
            await update.effective_message.reply_text(build_premium_card(t), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ В админку тайтла", callback_data=f"adm:t:view:{tid}")]]))
        return
    if data_str.startswith("adm:t:delete_yes:"):
        tid = data_str.split(":", 3)[3]
        titles = [t for t in await load_titles() if t.get("id") != tid]
        await save_titles(titles)
        for u in data.get("users", {}).values():
            if tid in u.get("favorites", []):
                u["favorites"] = [x for x in u.get("favorites", []) if x != tid]
            if tid in u.get("watched_150", []):
                u["watched_150"] = [x for x in u.get("watched_150", []) if x != tid]
            statuses = u.get("title_statuses", {})
            if isinstance(statuses, dict):
                statuses.pop(tid, None)
        for info in data.get("posts", {}).values():
            if info.get("title_id") == tid:
                info["title_id"] = None
        add_audit(data, admin_id, "title_delete", tid)
        await save_data(data)
        await show_admin_titles(update, context, data, 1)
        return
    if data_str.startswith("adm:t:delete:"):
        tid = data_str.split(":", 3)[3]
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("⚠️ Да, удалить", callback_data=f"adm:t:delete_yes:{tid}")],
                [InlineKeyboardButton("Отмена", callback_data=f"adm:t:view:{tid}")],
            ]
        )
        await _admin_render(update, f"⚠️ Удалить тайтл <code>{html_escape(tid)}</code>?\nБудут очищены ссылки из пользовательских списков и постов.", kb)
        return

    if data_str.startswith("adm:u:list:"):
        await show_admin_users(update, context, data, int(data_str.rsplit(":", 1)[1]))
        return
    if data_str == "adm:u:search":
        context.user_data["admin_pending"] = {"action": "user_search"}
        await update.effective_message.reply_text("🔎 Отправь Telegram ID, @username или часть имени.")
        return
    if data_str.startswith("adm:u:view:"):
        await show_admin_user_card(update, context, data, data_str.split(":", 3)[3])
        return
    if data_str.startswith("adm:u:access:"):
        _, _, _, uid, level = data_str.split(":", 4)
        if level in ACCESS_LEVELS:
            u = get_user(data, int(uid))
            u["access"] = level
            add_audit(data, admin_id, "user_access", uid, level)
            await save_data(data)
        await show_admin_user_card(update, context, data, uid)
        return
    if data_str.startswith("adm:u:ban:"):
        uid = data_str.split(":", 3)[3]
        if not is_root_admin(int(uid)):
            data.setdefault("banned", {})[uid] = True
            add_audit(data, admin_id, "user_ban", uid)
            await save_data(data)
        await show_admin_user_card(update, context, data, uid)
        return
    if data_str.startswith("adm:u:unban:"):
        uid = data_str.split(":", 3)[3]
        data.setdefault("banned", {}).pop(uid, None)
        add_audit(data, admin_id, "user_unban", uid)
        await save_data(data)
        await show_admin_user_card(update, context, data, uid)
        return
    if data_str.startswith("adm:u:message:"):
        uid = data_str.split(":", 3)[3]
        context.user_data["admin_pending"] = {"action": "user_message", "user_id": uid}
        await update.effective_message.reply_text(f"✉️ Отправь текст сообщения для пользователя <code>{uid}</code>.")
        return
    if data_str.startswith("adm:u:promote:") and is_root_admin(admin_id):
        uid = int(data_str.split(":", 3)[3])
        admins = data.setdefault("admins", [])
        if uid not in admins and uid not in ADMINS:
            admins.append(uid)
            add_audit(data, admin_id, "admin_add", str(uid))
            await save_data(data)
        await show_admin_user_card(update, context, data, str(uid))
        return
    if data_str.startswith("adm:u:demote:") and is_root_admin(admin_id):
        uid = int(data_str.split(":", 3)[3])
        if uid not in ADMINS:
            data["admins"] = [x for x in data.get("admins", []) if x != uid]
            add_audit(data, admin_id, "admin_remove", str(uid))
            await save_data(data)
        await show_admin_user_card(update, context, data, str(uid))
        return

    if data_str.startswith("adm:s:list:"):
        await show_admin_suggestions(update, context, data, int(data_str.rsplit(":", 1)[1]))
        return
    if data_str.startswith("adm:s:view:"):
        await show_admin_suggestion_card(update, context, data, data_str.split(":", 3)[3])
        return
    if data_str.startswith("adm:s:set:"):
        _, _, _, sid, status = data_str.split(":", 4)
        if status not in SUGGESTION_STATUS_LABELS:
            return
        item = data.get("suggestions", {}).get(sid)
        if item:
            item["status"] = status
            item["updated_at"] = int(time.time())
            add_audit(data, admin_id, "suggestion_status", sid, status)
            await save_data(data)
            try:
                await context.bot.send_message(
                    chat_id=item.get("user_id"),
                    text=f"📩 Статус твоего предложения #{sid} изменён: {SUGGESTION_STATUS_LABELS[status]}",
                )
            except Exception:
                pass
        await show_admin_suggestion_card(update, context, data, sid)
        return
    if data_str.startswith("adm:s:delete:"):
        sid = data_str.split(":", 3)[3]
        if sid in data.get("suggestions", {}):
            data["suggestions"].pop(sid, None)
            add_audit(data, admin_id, "suggestion_delete", sid)
            await save_data(data)
        await show_admin_suggestions(update, context, data, 1)
        return

    if data_str.startswith("adm:p:list:"):
        await show_admin_posts(update, context, data, int(data_str.rsplit(":", 1)[1]))
        return
    if data_str.startswith("adm:p:view:"):
        await show_admin_post_card(update, context, data, data_str.split(":", 3)[3])
        return
    if data_str.startswith("adm:p:link:"):
        mid = data_str.split(":", 3)[3]
        context.user_data["admin_pending"] = {"action": "post_link", "message_id": mid}
        await update.effective_message.reply_text("🔗 Отправь ID тайтла, который нужно привязать к посту.")
        return
    if data_str.startswith("adm:p:repost:"):
        mid = data_str.split(":", 3)[3]
        try:
            m = await context.bot.copy_message(chat_id=CHANNEL_USERNAME, from_chat_id=CHANNEL_USERNAME, message_id=int(mid))
        except Exception:
            logger.exception("Не удалось сделать репост поста %s", mid)
            await update.effective_message.reply_text("Не удалось пересоздать пост. Проверь права бота и существование сообщения.")
            return
        old = (await merged_channel_posts(data)).get(mid, {})
        data.setdefault("posts", {})[str(m.message_id)] = {
            "title_id": old.get("title_id"),
            "created_at": int(time.time()),
            "caption": old.get("caption"),
        }
        data["stats"]["reposts"] += 1
        data["stats"]["posts_created"] += 1
        add_audit(data, admin_id, "post_repost", mid, str(m.message_id))
        await save_data(data)
        await update.effective_message.reply_text(f"✅ Создан новый пост #{m.message_id}.")
        return
    if data_str.startswith("adm:p:delete_yes:"):
        mid = data_str.split(":", 3)[3]
        try:
            await context.bot.delete_message(chat_id=CHANNEL_USERNAME, message_id=int(mid))
        except Exception:
            logger.exception("Не удалось удалить пост %s", mid)
            await update.effective_message.reply_text("Не удалось удалить пост из канала. Проверь права бота.")
            return
        data.get("posts", {}).pop(mid, None)
        titles = await load_titles()
        changed_titles = False
        for title in titles:
            if str(title.get("channel_post_id") or "") == mid:
                title["channel_post_id"] = None
                title["channel_post_deleted"] = True
                changed_titles = True
        if changed_titles:
            await save_titles(titles)
        add_audit(data, admin_id, "post_delete", mid)
        await save_data(data)
        await show_admin_posts(update, context, data, 1)
        return
    if data_str.startswith("adm:p:delete:"):
        mid = data_str.split(":", 3)[3]
        await _admin_render(
            update,
            f"⚠️ Удалить пост <b>#{mid}</b> из канала? Это действие нельзя отменить.",
            InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("🗑 Да, удалить", callback_data=f"adm:p:delete_yes:{mid}")],
                    [InlineKeyboardButton("Отмена", callback_data=f"adm:p:view:{mid}")],
                ]
            ),
        )
        return

    if data_str == "adm:broadcast:start":
        context.user_data["admin_pending"] = {"action": "broadcast"}
        context.user_data.pop("admin_broadcast_text", None)
        await update.effective_message.reply_text(
            "📢 Отправь текст рассылки одним сообщением.\n\n"
            "Перед отправкой всем пользователям бот обязательно покажет предпросмотр и попросит подтверждение."
        )
        return
    if data_str == "adm:broadcast:cancel":
        context.user_data.pop("admin_broadcast_text", None)
        await show_admin_home(update, context, data)
        return
    if data_str == "adm:broadcast:confirm":
        message = context.user_data.pop("admin_broadcast_text", None)
        if not message:
            await update.effective_message.reply_text("Текст рассылки не найден. Создай рассылку заново.")
            return
        recipients = [int(uid) for uid, u in data.get("users", {}).items() if u.get("activated") and not data.get("banned", {}).get(uid)]
        sent = 0
        failed = 0
        progress = await update.effective_message.reply_text(f"📢 Рассылка началась. Получателей: {len(recipients)}")
        for uid in recipients:
            try:
                await context.bot.send_message(chat_id=uid, text=message, parse_mode=None)
                sent += 1
            except Exception:
                failed += 1
            await asyncio.sleep(0.04)
        data["stats"]["broadcasts_sent"] += 1
        data["stats"]["broadcast_recipients"] += sent
        add_audit(data, admin_id, "broadcast", "all", f"sent={sent}, failed={failed}")
        await save_data(data)
        await progress.edit_text(f"✅ Рассылка завершена.\nДоставлено: <b>{sent}</b>\nОшибок: <b>{failed}</b>")
        return

    if data_str == "adm:access":
        await show_admin_access(update, context, data)
        return
    if data_str == "adm:invite:friend":
        await _create_admin_access_invite(update, context, data, "friend")
        return
    if data_str == "adm:invite:vip":
        await _create_admin_access_invite(update, context, data, "vip")
        return
    if data_str == "adm:admin:add" and is_root_admin(admin_id):
        context.user_data["admin_pending"] = {"action": "admin_add"}
        await update.effective_message.reply_text("Отправь Telegram ID нового администратора.")
        return

    if data_str == "adm:system":
        await show_admin_system(update, context, data)
        return
    if data_str == "adm:system:backup":
        storage_dir = os.path.dirname(os.path.abspath(DATA_FILE)) or "."
        backup_dir = os.path.join(storage_dir, "backups")
        os.makedirs(backup_dir, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        copied = []
        for src, label in ((DATA_FILE, "bot_data"), (TITLES_FILE, "titles")):
            if os.path.exists(src):
                dst = os.path.join(backup_dir, f"{label}_{stamp}.json")
                shutil.copy2(src, dst)
                set_private_permissions(dst)
                copied.append(os.path.basename(dst))
        add_audit(data, admin_id, "backup", "system", ", ".join(copied))
        await save_data(data)
        await update.effective_message.reply_text(
            "💾 Резервная копия создана.\n" + "\n".join(f"• <code>{html_escape(x)}</code>" for x in copied)
        )
        return

    if data_str == "adm:audit":
        await show_admin_audit(update, context, data)
        return
    if data_str == "adm:audit:clear_confirm" and is_root_admin(admin_id):
        await _admin_render(
            update,
            "⚠️ Очистить журнал действий администраторов?",
            InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("Да, очистить", callback_data="adm:audit:clear_yes")],
                    [InlineKeyboardButton("Отмена", callback_data="adm:audit")],
                ]
            ),
        )
        return
    if data_str == "adm:audit:clear_yes" and is_root_admin(admin_id):
        data["audit_log"] = []
        add_audit(data, admin_id, "audit_clear")
        await save_data(data)
        await show_admin_audit(update, context, data)
        return


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

    if data_str.startswith("adm:"):
        await handle_admin_callback(update, context, data, data_str)
        return

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

    if data_str == "draft_publish":
        if not is_admin(data, user_id):
            await query.answer("Эта кнопка доступна только администратору.", show_alert=True)
            return

        draft = context.user_data.get("draft_post")
        if not draft:
            try:
                await query.edit_message_reply_markup(reply_markup=None)
            except Exception:
                pass
            await query.message.reply_text(
                "Черновик уже опубликован, отменён или потерян после перезапуска бота."
            )
            return

        photo = draft.get("photo")
        caption = draft.get("caption", "")
        markup = draft.get("reply_markup")
        title_id = draft.get("title_id")

        if not photo:
            context.user_data.pop("draft_post", None)
            await query.message.reply_text("Черновик повреждён: отсутствует изображение.")
            return

        try:
            m = await context.bot.send_photo(
                chat_id=CHANNEL_USERNAME,
                photo=photo,
                caption=caption,
                reply_markup=markup,
            )
        except Exception:
            logger.exception("Не удалось опубликовать черновик в канал")
            await query.message.reply_text(
                "Не удалось опубликовать черновик. Проверь права бота в канале. "
                "Технические детали записаны в серверный лог."
            )
            return

        posts = data.get("posts", {})
        posts[str(m.message_id)] = {
            "title_id": title_id,
            "created_at": int(time.time()),
            "caption": caption,
        }
        data["posts"] = posts
        data["stats"]["posts_created"] += 1
        add_audit(data, user_id, "draft_publish", str(m.message_id))
        await save_data(data)

        context.user_data.pop("draft_post", None)
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass

        await query.message.reply_text(
            f"Пост опубликован в канал ✅\nID сообщения: <code>{m.message_id}</code>"
        )
        return

    if data_str == "draft_cancel":
        if not is_admin(data, user_id):
            await query.answer("Эта кнопка доступна только администратору.", show_alert=True)
            return

        context.user_data.pop("draft_post", None)
        try:
            await query.message.delete()
        except Exception:
            try:
                await query.edit_message_reply_markup(reply_markup=None)
            except Exception:
                pass

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Черновик отменён ❌",
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

    if data_str == "prof_favorites":
        await handle_favorites(update, context)
        return

    if data_str == "prof_top150":
        await handle_watched_list(update, context)
        return

    if data_str == "prof_friends":
        await handle_friend_list(update, context)
        return

    if data_str == "catnoop":
        return

    if data_str.startswith("catpage:"):
        try:
            page = int(data_str.split(":", 1)[1])
        except ValueError:
            page = 1
        titles = await load_titles()
        text, kb = build_catalog_page(titles, user_data, page)
        await query.edit_message_text(text, reply_markup=kb)
        return

    if data_str.startswith("cat:"):
        tid = data_str.split(":", 1)[1]
        title = TITLES_BY_ID.get(tid)
        if not title:
            await query.edit_message_text("Тайтл не найден.")
            return
        required = title.get("min_access", "free")
        if not has_access(user_data, required):
            await query.answer("Недостаточный уровень доступа.", show_alert=True)
            return
        sync_watched_150_rule_b(user_data, title)
        await save_data(data)
        await query.edit_message_text(build_premium_card(title, user_data=user_data), reply_markup=build_title_keyboard(title, user_data))
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


def is_valid_button_url(value: str) -> bool:
    value = (value or "").strip()
    return bool(re.fullmatch(r"https?://[^\s]+", value))


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
    caption = update.message.text or ""
    if len(caption) > 1024:
        await update.effective_message.reply_text(
            f"Подпись слишком длинная: {len(caption)}/1024 символов. Сократи текст и отправь снова."
        )
        return POST_CAPTION
    context.user_data["post_caption"] = caption
    await update.effective_message.reply_text(
        "Шаг 3/4.\nВставь ссылку на описание (Telegraph).\n"
        "Если описания пока нет — напиши <code>-</code>."
    )
    return POST_DESC


async def post_get_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    desc_link = (update.message.text or "").strip()
    if desc_link == "-":
        desc_link = None
    elif not is_valid_button_url(desc_link):
        await update.effective_message.reply_text(
            "Нужна полная ссылка вида <code>https://...</code> или <code>-</code>."
        )
        return POST_DESC
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
    elif not is_valid_button_url(watch_link):
        await update.effective_message.reply_text(
            "Нужна полная ссылка вида <code>https://...</code> или <code>-</code>."
        )
        return POST_WATCH

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
            add_audit(data, update.effective_user.id, "post_publish", str(m.message_id))
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
            add_audit(data, update.effective_user.id, "draft_create")
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
    if len(caption) > 1024:
        await update.effective_message.reply_text(
            f"Подпись слишком длинная: {len(caption)}/1024 символов. Сократи текст и отправь снова."
        )
        return EDIT_CAPTION
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
    elif not is_valid_button_url(desc_link):
        await update.effective_message.reply_text(
            "Нужна полная ссылка вида <code>https://...</code> или <code>-</code>."
        )
        return EDIT_DESC
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
    elif not is_valid_button_url(watch_link):
        await update.effective_message.reply_text(
            "Нужна полная ссылка вида <code>https://...</code> или <code>-</code>."
        )
        return EDIT_WATCH

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
        add_audit(data, update.effective_user.id, "post_edit", str(msg_id))
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
    add_audit(data, user_id, "post_link_command", str(msg_id), tid)
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
        add_audit(data, user_id, "post_repost_command", str(msg_id), str(m.message_id))
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
            CallbackQueryHandler(admin_post_start_draft_cb, pattern=r"^adm:post:new_draft$"),
            CallbackQueryHandler(admin_post_start_direct_cb, pattern=r"^adm:post:new_direct$"),
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
        entry_points=[
            CommandHandler("edit_post", edit_post_start),
            CallbackQueryHandler(admin_edit_post_start_cb, pattern=r"^adm:post:edit:\d+$"),
        ],
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
    application.add_handler(CommandHandler("admin", admin_command))
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
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_text_input))
    application.add_handler(CallbackQueryHandler(handle_buttons))
    application.add_error_handler(handle_unexpected_error)

    if not ACCESS_CODES:
        logger.warning(
            "ACCESS_CODE_VIP / ACCESS_CODE_FRIEND не заданы: команда /code не выдаст повышенный доступ."
        )

    try:
        application.run_polling(drop_pending_updates=DROP_PENDING_UPDATES)
    except InvalidToken:
        # Не пробрасываем исходное исключение наружу: некоторые версии библиотеки
        # включают сам BOT_TOKEN в текст InvalidToken.
        logger.critical(
            "Telegram отклонил BOT_TOKEN. Проверьте значение BOT_TOKEN "
            "в переменных окружения хостинга."
        )
        raise SystemExit(2)


if __name__ == "__main__":
    main()
