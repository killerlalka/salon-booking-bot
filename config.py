"""Настройки бота. Всё, что меняется под конкретного клиента, — здесь."""

import os
from datetime import time, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_env(path: Path) -> None:
    """Читает файл .env (КЛЮЧ=значение) в переменные окружения."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env(BASE_DIR / ".env")

# --- Секреты и окружение (из файла .env) ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = {
    int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x.isdigit()
}
TZ = timezone(timedelta(hours=int(os.getenv("TZ_OFFSET", "3"))))  # Беларусь: UTC+3
DB_PATH = BASE_DIR / "bookings.db"

# --- Информация о салоне ---
SALON = {
    "name": "Салон красоты «Лаванда»",
    "address": "г. Витебск, ул. Примерная, 1",
    "phone": "+375 29 000-00-00",
    "hours": "Пн–Сб: 9:00–20:00, Вс — выходной",
}

# --- Услуги: id, название, цена (BYN), длительность (мин) ---
SERVICES = [
    {"id": 1, "emoji": "💇‍♀️", "title": "Женская стрижка", "price": 35, "duration": 60},
    {"id": 2, "emoji": "💇‍♂️", "title": "Мужская стрижка", "price": 20, "duration": 30},
    {"id": 3, "emoji": "🎨", "title": "Окрашивание", "price": 90, "duration": 120},
    {"id": 4, "emoji": "💅", "title": "Маникюр с покрытием", "price": 40, "duration": 90},
    {"id": 5, "emoji": "✨", "title": "Укладка", "price": 25, "duration": 30},
]
SERVICES_BY_ID = {s["id"]: s for s in SERVICES}

# --- Мастера: у каждого своё расписание; services — какие услуги он делает ---
MASTERS = [
    {"id": 1, "name": "Ольга", "role": "стилист-парикмахер", "services": [1, 2, 3, 5]},
    {"id": 2, "name": "Дмитрий", "role": "барбер", "services": [2]},
    {"id": 3, "name": "Ирина", "role": "мастер маникюра", "services": [4]},
]
MASTERS_BY_ID = {m["id"]: m for m in MASTERS}

# --- Расписание ---
WORK_START = time(9, 0)
WORK_END = time(20, 0)
DAYS_OFF = {6}             # дни недели без записи: 0 = Пн ... 6 = Вс
SLOT_STEP_MIN = 30         # шаг сетки времени
DAYS_AHEAD = 7             # на сколько дней вперёд открыта запись
MIN_LEAD_MIN = 60          # не раньше чем через столько минут от текущего момента
REMIND_BEFORE_HOURS = 2    # за сколько часов напомнить клиенту
