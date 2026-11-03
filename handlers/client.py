"""Сценарий клиента: меню, запись, мои записи, услуги, контакты."""

import re
from datetime import datetime, timedelta
from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

import config
import database
import keyboards as kb
import schedule
from keyboards import CancelCb, DayCb, MasterCb, ServiceCb, TimeCb
from notifications import notify_admins

router = Router()


class Booking(StatesGroup):
    master = State()
    day = State()
    time = State()
    name = State()
    phone = State()
    confirm = State()


def welcome_text(first_name: str) -> str:
    return (
        f"Здравствуйте, {escape(first_name)}! 👋\n\n"
        f"Я бот <b>{config.SALON['name']}</b>.\n"
        "Помогу записаться на услугу за минуту — без звонков и ожидания.\n\n"
        "Выберите, что вас интересует:"
    )


def booking_summary(data: dict) -> str:
    service = config.SERVICES_BY_ID[data["service_id"]]
    starts_at = datetime.fromisoformat(data["starts_at"])
    master = config.MASTERS_BY_ID[data["assigned_master_id"]]
    return (
        f"💇 Услуга: <b>{service['title']}</b>\n"
        f"👤 Мастер: <b>{master['name']}</b>\n"
        f"📅 Дата: <b>{schedule.fmt_date(starts_at.date())}</b>\n"
        f"🕐 Время: <b>{schedule.fmt_period(starts_at, service['duration'])}</b>\n"
        f"💰 Стоимость: <b>{service['price']} р.</b>\n"
        f"👤 Имя: <b>{escape(data['name'])}</b>\n"
        f"📱 Телефон: <b>{data['phone']}</b>"
    )


# ---------- Меню ----------

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(welcome_text(message.from_user.first_name), reply_markup=kb.main_menu())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=ReplyKeyboardRemove())
    await message.answer(welcome_text(message.from_user.first_name), reply_markup=kb.main_menu())


@router.message(Command("myid"))
async def cmd_myid(message: Message):
    await message.answer(f"Ваш Telegram ID: <code>{message.from_user.id}</code>")


@router.callback_query(F.data == "menu")
async def cb_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text(welcome_text(cb.from_user.first_name), reply_markup=kb.main_menu())
    await cb.answer()


@router.callback_query(F.data == "services")
async def cb_services(cb: CallbackQuery):
    lines = [
        f"{s['emoji']} <b>{s['title']}</b> — {s['price']} р. · {s['duration']} мин"
        for s in config.SERVICES
    ]
    await cb.message.edit_text("💅 <b>Услуги и цены</b>\n\n" + "\n".join(lines),
                               reply_markup=kb.services_info())
    await cb.answer()


@router.callback_query(F.data == "contacts")
async def cb_contacts(cb: CallbackQuery):
    s = config.SALON
    await cb.message.edit_text(
        f"📍 <b>{s['name']}</b>\n\n"
        f"Адрес: {s['address']}\n"
        f"Телефон: {s['phone']}\n"
        f"Часы работы: {s['hours']}",
        reply_markup=kb.back_to_menu(),
    )
    await cb.answer()


# ---------- Запись: услуга → дата → время → имя → телефон → подтверждение ----------

@router.message(Command("book"))
async def cmd_book(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Выберите услугу:", reply_markup=kb.services())


@router.callback_query(F.data == "book")
async def cb_book(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("Выберите услугу:", reply_markup=kb.services())
    await cb.answer()


def master_label(master_id: int) -> str:
    return f"👤 {config.MASTERS_BY_ID[master_id]['name']}" if master_id else "✨ Любой свободный мастер"


async def show_masters(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    service = config.SERVICES_BY_ID[data["service_id"]]
    await state.set_state(Booking.master)
    await cb.message.edit_text(
        f"{service['emoji']} <b>{service['title']}</b> · {service['price']} р.\n\n"
        "К кому хотите записаться?",
        reply_markup=kb.masters(schedule.masters_for(service["id"])),
    )


async def show_days(cb: CallbackQuery, state: FSMContext, note: str = ""):
    data = await state.get_data()
    service = config.SERVICES_BY_ID[data["service_id"]]
    available = schedule.available_days(service, data["master_id"])
    if not available:
        await cb.message.edit_text(
            f"😔 На ближайшие {config.DAYS_AHEAD} дней свободного времени на "
            f"«{service['title']}» нет. Позвоните нам: {config.SALON['phone']}",
            reply_markup=kb.back_to_menu(),
        )
        await state.clear()
        return
    await state.set_state(Booking.day)
    await cb.message.edit_text(
        f"{note}{service['emoji']} <b>{service['title']}</b> · {service['price']} р.\n"
        f"{master_label(data['master_id'])}\n\n"
        "Выберите дату:",
        reply_markup=kb.days(available, back_to_masters=len(schedule.masters_for(service["id"])) > 1),
    )


@router.callback_query(ServiceCb.filter())
async def cb_service(cb: CallbackQuery, callback_data: ServiceCb, state: FSMContext):
    if callback_data.id not in config.SERVICES_BY_ID:
        await cb.answer("Услуга не найдена", show_alert=True)
        return
    await state.clear()
    masters = schedule.masters_for(callback_data.id)
    if len(masters) == 1:
        # Выбирать не из кого — сразу к датам
        await state.update_data(service_id=callback_data.id, master_id=masters[0]["id"])
        await show_days(cb, state)
    else:
        await state.update_data(service_id=callback_data.id)
        await show_masters(cb, state)
    await cb.answer()


@router.callback_query(Booking.master, MasterCb.filter())
async def cb_master(cb: CallbackQuery, callback_data: MasterCb, state: FSMContext):
    data = await state.get_data()
    allowed = {m["id"] for m in schedule.masters_for(data["service_id"])}
    if callback_data.id and callback_data.id not in allowed:
        await cb.answer("Этот мастер не делает эту услугу", show_alert=True)
        return
    await state.update_data(master_id=callback_data.id)
    await show_days(cb, state)
    await cb.answer()


@router.callback_query(Booking.day, F.data == "back_masters")
async def cb_back_masters(cb: CallbackQuery, state: FSMContext):
    await show_masters(cb, state)
    await cb.answer()


async def show_times(cb: CallbackQuery, state: FSMContext, note: str = ""):
    data = await state.get_data()
    service = config.SERVICES_BY_ID[data["service_id"]]
    day = datetime.strptime(data["day"], "%Y%m%d").date()
    slots = schedule.slots_for(day, service, data["master_id"])
    if not slots:
        await show_days(cb, state, note="😔 На этот день всё занято.\n\n")
        return
    await state.set_state(Booking.time)
    await cb.message.edit_text(
        f"{note}{service['emoji']} <b>{service['title']}</b>\n"
        f"{master_label(data['master_id'])}\n"
        f"📅 {schedule.fmt_date(day)}\n\n"
        "Выберите время:",
        reply_markup=kb.times(slots),
    )


@router.callback_query(Booking.day, DayCb.filter())
async def cb_day(cb: CallbackQuery, callback_data: DayCb, state: FSMContext):
    await state.update_data(day=callback_data.d)
    await show_times(cb, state)
    await cb.answer()


@router.callback_query(Booking.time, F.data == "back_days")
async def cb_back_days(cb: CallbackQuery, state: FSMContext):
    await show_days(cb, state)
    await cb.answer()


@router.callback_query(Booking.time, TimeCb.filter())
async def cb_time(cb: CallbackQuery, callback_data: TimeCb, state: FSMContext):
    data = await state.get_data()
    service = config.SERVICES_BY_ID[data["service_id"]]
    starts_at = datetime.strptime(data["day"] + callback_data.t, "%Y%m%d%H%M")
    master = schedule.pick_master(starts_at, service, data["master_id"])
    if not master:
        await cb.answer("Это время только что заняли, выберите другое", show_alert=True)
        await show_times(cb, state)
        return

    suggested = database.last_name(cb.from_user.id) or cb.from_user.first_name
    await state.update_data(starts_at=starts_at.isoformat(), suggested_name=suggested,
                            assigned_master_id=master["id"])
    await state.set_state(Booking.name)
    await cb.message.edit_text(
        f"🕐 {schedule.fmt_date(starts_at.date())}, {starts_at:%H:%M} · мастер {master['name']}\n\n"
        "Как к вам обращаться? Напишите имя или нажмите кнопку:",
        reply_markup=kb.name(suggested),
    )
    await cb.answer()


async def ask_phone(message: Message, state: FSMContext):
    await state.set_state(Booking.phone)
    await message.answer(
        "📱 Оставьте номер телефона — мастер свяжется, если что-то изменится.\n\n"
        "Нажмите кнопку ниже или напишите номер вручную.",
        reply_markup=kb.phone(),
    )


@router.callback_query(Booking.name, F.data == "use_name")
async def cb_use_name(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.update_data(name=data["suggested_name"])
    await cb.message.edit_reply_markup(reply_markup=None)
    await ask_phone(cb.message, state)
    await cb.answer()


@router.message(Booking.name, F.text)
async def msg_name(message: Message, state: FSMContext):
    name = message.text.strip()[:50]
    if len(name) < 2 or name.startswith("/"):
        await message.answer("Напишите, пожалуйста, ваше имя (минимум 2 буквы).")
        return
    await state.update_data(name=name)
    await ask_phone(message, state)


async def show_confirm(message: Message, state: FSMContext, phone: str):
    await state.update_data(phone=phone)
    await state.set_state(Booking.confirm)
    await message.answer("Номер сохранён 👍", reply_markup=ReplyKeyboardRemove())
    data = await state.get_data()
    await message.answer("<b>Проверьте запись:</b>\n\n" + booking_summary(data) + "\n\nВсё верно?",
                         reply_markup=kb.confirm())


@router.message(Booking.phone, F.contact)
async def msg_contact(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone
    await show_confirm(message, state, phone)


@router.message(Booking.phone, F.text)
async def msg_phone(message: Message, state: FSMContext):
    digits = re.sub(r"\D", "", message.text)
    if not 9 <= len(digits) <= 15:
        await message.answer("Не похоже на номер телефона 🤔 Пример: +375 29 123-45-67")
        return
    phone = ("+" if message.text.strip().startswith("+") else "") + digits
    await show_confirm(message, state, phone)


@router.callback_query(Booking.confirm, F.data == "confirm")
async def cb_confirm(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    service = config.SERVICES_BY_ID[data["service_id"]]
    starts_at = datetime.fromisoformat(data["starts_at"])

    # Сначала тот же мастер; если клиент выбрал «любого» — подойдёт любой свободный
    master = schedule.pick_master(starts_at, service, data["assigned_master_id"])
    if not master and not data["master_id"]:
        master = schedule.pick_master(starts_at, service, None)
    if not master:
        await cb.answer("Увы, это время только что заняли", show_alert=True)
        await show_days(cb, state, note="😔 Выбранное время уже занято, выберите другое.\n\n")
        return
    await state.update_data(assigned_master_id=master["id"])
    data = await state.get_data()

    # Если до визита меньше окна напоминания — отдельное напоминание не нужно.
    soon = starts_at - schedule.now() <= timedelta(hours=config.REMIND_BEFORE_HOURS)
    booking_id = database.add(cb.from_user.id, data["name"], data["phone"], service, master,
                              starts_at, reminded=soon)
    await state.clear()

    await cb.message.edit_text(
        "✅ <b>Вы записаны!</b>\n\n"
        + booking_summary(data)
        + f"\n\n📍 {config.SALON['address']}\n\n"
        f"Напомню о визите за {config.REMIND_BEFORE_HOURS} ч. "
        "Отменить запись можно в разделе «Мои записи».",
        reply_markup=kb.back_to_menu(),
    )
    await cb.answer("Готово!")

    username = f"\n💬 @{cb.from_user.username}" if cb.from_user.username else ""
    await notify_admins(
        cb.bot,
        f"🆕 <b>Новая запись #{booking_id}</b>\n\n" + booking_summary(data) + escape(username),
    )


@router.callback_query(F.data == "cancel_booking")
async def cb_cancel_booking(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("Запись не оформлена. Возвращайтесь, когда будет удобно 🙂",
                               reply_markup=kb.back_to_menu())
    await cb.answer()


# ---------- Мои записи ----------

async def render_my(cb: CallbackQuery):
    bookings = database.upcoming_for_user(cb.from_user.id, schedule.now())
    if not bookings:
        text = "🗂 У вас пока нет предстоящих записей."
    else:
        lines = [
            f"• <b>{schedule.fmt_date(b.starts_at.date())}, {b.starts_at:%H:%M}</b> — "
            f"{b.service_title}, мастер {b.master_name}, {b.price} р."
            for b in bookings
        ]
        text = "🗂 <b>Ваши записи</b>\n\n" + "\n".join(lines)
    await cb.message.edit_text(text, reply_markup=kb.my_bookings(bookings))


@router.callback_query(F.data == "my")
async def cb_my(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await render_my(cb)
    await cb.answer()


@router.callback_query(CancelCb.filter())
async def cb_cancel(cb: CallbackQuery, callback_data: CancelCb):
    b = database.get(callback_data.id)
    if not b or b.user_id != cb.from_user.id or b.status != "active":
        await cb.answer("Запись не найдена", show_alert=True)
        return
    database.cancel(b.id)
    await cb.answer("Запись отменена")
    await render_my(cb)
    await notify_admins(
        cb.bot,
        f"❌ <b>Клиент отменил запись #{b.id}</b>\n\n"
        f"{b.service_title} · мастер {b.master_name}\n"
        f"📅 {schedule.fmt_date(b.starts_at.date())}, {b.starts_at:%H:%M}\n"
        f"👤 {escape(b.name)}, {b.phone}",
    )


# ---------- Всё остальное ----------

@router.message()
async def fallback(message: Message):
    await message.answer("Не совсем понял вас 🙂 Нажмите /start, чтобы открыть меню.")


@router.callback_query()
async def fallback_callback(cb: CallbackQuery):
    await cb.answer("Эта кнопка устарела. Нажмите /start, чтобы открыть меню.", show_alert=True)
