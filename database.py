"""Хранение записей в SQLite (файл bookings.db рядом с ботом)."""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime

from config import DB_PATH

DT_FMT = "%Y-%m-%d %H:%M"


@dataclass
class Booking:
    id: int
    user_id: int
    name: str
    phone: str
    service_id: int
    service_title: str
    price: int
    duration: int
    starts_at: datetime
    status: str
    reminded: bool
    master_id: int
    master_name: str


@contextmanager
def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _to_booking(row: sqlite3.Row) -> Booking:
    return Booking(
        id=row["id"],
        user_id=row["user_id"],
        name=row["name"],
        phone=row["phone"],
        service_id=row["service_id"],
        service_title=row["service_title"],
        price=row["price"],
        duration=row["duration"],
        starts_at=datetime.strptime(row["starts_at"], DT_FMT),
        status=row["status"],
        reminded=bool(row["reminded"]),
        master_id=row["master_id"],
        master_name=row["master_name"],
    )


def init() -> None:
    with _db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bookings (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER NOT NULL,
                name          TEXT    NOT NULL,
                phone         TEXT    NOT NULL,
                service_id    INTEGER NOT NULL,
                service_title TEXT    NOT NULL,
                price         INTEGER NOT NULL,
                duration      INTEGER NOT NULL,
                starts_at     TEXT    NOT NULL,
                status        TEXT    NOT NULL DEFAULT 'active',
                reminded      INTEGER NOT NULL DEFAULT 0,
                created_at    TEXT    NOT NULL,
                master_id     INTEGER NOT NULL DEFAULT 1,
                master_name   TEXT    NOT NULL DEFAULT ''
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_starts ON bookings(starts_at)")
        # База от старой версии бота (без мастеров) — добавляем недостающие колонки
        columns = {r["name"] for r in conn.execute("PRAGMA table_info(bookings)")}
        if "master_id" not in columns:
            conn.execute("ALTER TABLE bookings ADD COLUMN master_id INTEGER NOT NULL DEFAULT 1")
        if "master_name" not in columns:
            conn.execute("ALTER TABLE bookings ADD COLUMN master_name TEXT NOT NULL DEFAULT ''")


def add(user_id: int, name: str, phone: str, service: dict, master: dict, starts_at: datetime,
        reminded: bool = False) -> int:
    with _db() as conn:
        cur = conn.execute(
            """
            INSERT INTO bookings (user_id, name, phone, service_id, service_title, price,
                                  duration, starts_at, reminded, created_at, master_id, master_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, name, phone, service["id"], service["title"], service["price"],
             service["duration"], starts_at.strftime(DT_FMT), int(reminded),
             datetime.now().strftime(DT_FMT), master["id"], master["name"]),
        )
        return cur.lastrowid


def get(booking_id: int) -> Booking | None:
    with _db() as conn:
        row = conn.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
    return _to_booking(row) if row else None


def between(start: datetime, end: datetime, master_id: int | None = None) -> list[Booking]:
    """Активные записи, начинающиеся в промежутке [start, end) — все или одного мастера."""
    query = "SELECT * FROM bookings WHERE status = 'active' AND starts_at >= ? AND starts_at < ?"
    params: list = [start.strftime(DT_FMT), end.strftime(DT_FMT)]
    if master_id is not None:
        query += " AND master_id = ?"
        params.append(master_id)
    with _db() as conn:
        rows = conn.execute(query + " ORDER BY starts_at", params).fetchall()
    return [_to_booking(r) for r in rows]


def upcoming_for_user(user_id: int, after: datetime) -> list[Booking]:
    with _db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM bookings
            WHERE status = 'active' AND user_id = ? AND starts_at >= ?
            ORDER BY starts_at
            """,
            (user_id, after.strftime(DT_FMT)),
        ).fetchall()
    return [_to_booking(r) for r in rows]


def last_name(user_id: int) -> str | None:
    """Имя, которое клиент указывал в прошлый раз."""
    with _db() as conn:
        row = conn.execute(
            "SELECT name FROM bookings WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,)
        ).fetchone()
    return row["name"] if row else None


def cancel(booking_id: int) -> None:
    with _db() as conn:
        conn.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?", (booking_id,))


def due_reminders(now: datetime, until: datetime) -> list[Booking]:
    with _db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM bookings
            WHERE status = 'active' AND reminded = 0 AND starts_at > ? AND starts_at <= ?
            """,
            (now.strftime(DT_FMT), until.strftime(DT_FMT)),
        ).fetchall()
    return [_to_booking(r) for r in rows]


def set_reminded(booking_id: int) -> None:
    with _db() as conn:
        conn.execute("UPDATE bookings SET reminded = 1 WHERE id = ?", (booking_id,))
