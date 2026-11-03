"""Свободное время и форматирование дат."""

from datetime import date, datetime, timedelta

import config
import database

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля",
          "августа", "сентября", "октября", "ноября", "декабря"]


def now() -> datetime:
    """Текущее время салона (без часового пояса, с точностью до минуты)."""
    return datetime.now(config.TZ).replace(tzinfo=None, second=0, microsecond=0)


def masters_for(service_id: int) -> list[dict]:
    return [m for m in config.MASTERS if service_id in m["services"]]


def free_slots(day: date, duration: int, master_id: int) -> list[datetime]:
    """Время начала, на которое можно записаться к мастеру на услугу длительностью duration минут."""
    if day.weekday() in config.DAYS_OFF:
        return []

    day_start = datetime.combine(day, config.WORK_START)
    day_end = datetime.combine(day, config.WORK_END)
    busy = [
        (b.starts_at, b.starts_at + timedelta(minutes=b.duration))
        for b in database.between(day_start, day_end, master_id)
    ]
    earliest = now() + timedelta(minutes=config.MIN_LEAD_MIN)
    length = timedelta(minutes=duration)
    step = timedelta(minutes=config.SLOT_STEP_MIN)

    slots = []
    t = day_start
    while t + length <= day_end:
        overlaps = any(t < busy_end and t + length > busy_start for busy_start, busy_end in busy)
        if t >= earliest and not overlaps:
            slots.append(t)
        t += step
    return slots


def _candidates(service: dict, master_id: int | None) -> list[dict]:
    """Мастер, выбранный клиентом, или все мастера, которые делают услугу (вариант «любой»)."""
    if master_id:
        return [config.MASTERS_BY_ID[master_id]]
    return masters_for(service["id"])


def slots_for(day: date, service: dict, master_id: int | None) -> list[datetime]:
    """Свободное время у выбранного мастера или хотя бы у одного из подходящих."""
    slots = set()
    for m in _candidates(service, master_id):
        slots.update(free_slots(day, service["duration"], m["id"]))
    return sorted(slots)


def available_days(service: dict, master_id: int | None) -> list[date]:
    today = now().date()
    days = (today + timedelta(days=i) for i in range(config.DAYS_AHEAD))
    return [d for d in days if slots_for(d, service, master_id)]


def pick_master(starts_at: datetime, service: dict, master_id: int | None) -> dict | None:
    """Мастер, который свободен в это время (для «любого» — первый свободный), или None."""
    for m in _candidates(service, master_id):
        if starts_at in free_slots(starts_at.date(), service["duration"], m["id"]):
            return m
    return None


def fmt_date(d: date) -> str:
    return f"{WEEKDAYS[d.weekday()]}, {d.day} {MONTHS[d.month - 1]}"


def fmt_period(starts_at: datetime, duration: int) -> str:
    ends_at = starts_at + timedelta(minutes=duration)
    return f"{starts_at:%H:%M}–{ends_at:%H:%M}"
