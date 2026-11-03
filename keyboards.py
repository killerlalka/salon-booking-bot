"""Кнопки бота."""

from datetime import date, datetime

from aiogram.filters.callback_data import CallbackData
from aiogram.types import (InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton,
                           ReplyKeyboardMarkup)
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
from database import Booking
from schedule import WEEKDAYS, MONTHS


class ServiceCb(CallbackData, prefix="svc"):
    id: int


class MasterCb(CallbackData, prefix="mst"):
    id: int  # 0 — любой свободный мастер


class DayCb(CallbackData, prefix="day"):
    d: str  # YYYYMMDD


class TimeCb(CallbackData, prefix="tm"):
    t: str  # HHMM


class CancelCb(CallbackData, prefix="cnl"):
    id: int


class AdminDayCb(CallbackData, prefix="adm"):
    days: int  # 0 — сегодня, 1 — завтра, 7 — неделя


class AdminCancelCb(CallbackData, prefix="acnl"):
    id: int


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


MENU_BTN = _btn("🏠 В меню", "menu")


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("📅 Записаться", "book")],
        [_btn("🗂 Мои записи", "my")],
        [_btn("💅 Услуги и цены", "services"), _btn("📍 Контакты", "contacts")],
    ])


def back_to_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[MENU_BTN]])


def services_info() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("📅 Записаться", "book")], [MENU_BTN]])


def services() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for s in config.SERVICES:
        kb.button(text=f"{s['emoji']} {s['title']} — {s['price']} р.",
                  callback_data=ServiceCb(id=s["id"]).pack())
    kb.adjust(1)
    kb.row(MENU_BTN)
    return kb.as_markup()


def masters(masters_list: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✨ Любой свободный мастер", callback_data=MasterCb(id=0).pack())
    for m in masters_list:
        kb.button(text=f"👤 {m['name']} — {m['role']}", callback_data=MasterCb(id=m["id"]).pack())
    kb.adjust(1)
    kb.row(_btn("⬅️ К услугам", "book"), _btn("✖️ Отмена", "cancel_booking"))
    return kb.as_markup()


def days(available: list[date], back_to_masters: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for d in available:
        kb.button(text=f"{WEEKDAYS[d.weekday()]}, {d.day} {MONTHS[d.month - 1][:4]}.",
                  callback_data=DayCb(d=d.strftime("%Y%m%d")).pack())
    kb.adjust(2)
    back = _btn("⬅️ К мастерам", "back_masters") if back_to_masters else _btn("⬅️ К услугам", "book")
    kb.row(back, _btn("✖️ Отмена", "cancel_booking"))
    return kb.as_markup()


def times(slots: list[datetime]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for t in slots:
        kb.button(text=t.strftime("%H:%M"), callback_data=TimeCb(t=t.strftime("%H%M")).pack())
    kb.adjust(4)
    kb.row(_btn("⬅️ К датам", "back_days"), _btn("✖️ Отмена", "cancel_booking"))
    return kb.as_markup()


def name(suggested: str | None) -> InlineKeyboardMarkup:
    rows = []
    if suggested:
        rows.append([_btn(f"👤 {suggested}", "use_name")])
    rows.append([_btn("✖️ Отмена", "cancel_booking")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def phone() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить мой номер", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="+375 29 123-45-67",
    )


def confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("✅ Подтвердить", "confirm")],
        [_btn("✖️ Отменить", "cancel_booking")],
    ])


def my_bookings(bookings: list[Booking]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for b in bookings:
        d = b.starts_at
        kb.button(text=f"❌ Отменить {d.day} {MONTHS[d.month - 1][:4]}. {d:%H:%M}",
                  callback_data=CancelCb(id=b.id).pack())
    kb.adjust(1)
    kb.row(_btn("📅 Новая запись", "book"), MENU_BTN)
    return kb.as_markup()


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        _btn("📋 Сегодня", AdminDayCb(days=0).pack()),
        _btn("📋 Завтра", AdminDayCb(days=1).pack()),
        _btn("🗓 Неделя", AdminDayCb(days=7).pack()),
    ]])


def admin_bookings(bookings: list[Booking]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for b in bookings[:30]:
        kb.button(text=f"❌ {b.starts_at:%d.%m %H:%M} · {b.master_name} · {b.name}",
                  callback_data=AdminCancelCb(id=b.id).pack())
    kb.adjust(1)
    kb.row(*admin_menu().inline_keyboard[0])
    return kb.as_markup()
