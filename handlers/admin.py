"""Панель администратора: записи на сегодня / завтра / неделю, отмена записей."""

from datetime import datetime, timedelta
from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

import config
import database
import keyboards as kb
import schedule
from keyboards import AdminCancelCb, AdminDayCb

router = Router()
router.message.filter(F.from_user.id.in_(config.ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(config.ADMIN_IDS))


def day_range(days: int) -> tuple[datetime, datetime, str]:
    today = datetime.combine(schedule.now().date(), datetime.min.time())
    if days == 0:
        return today, today + timedelta(days=1), "Сегодня"
    if days == 1:
        return today + timedelta(days=1), today + timedelta(days=2), "Завтра"
    return today, today + timedelta(days=days), f"Ближайшие {days} дней"


def render_bookings(title: str, bookings: list[database.Booking]) -> str:
    if not bookings:
        return f"📋 <b>{title}</b>\n\nЗаписей нет."

    parts = [f"📋 <b>{title}</b>"]
    current_day = None
    for b in bookings:
        if b.starts_at.date() != current_day:
            current_day = b.starts_at.date()
            parts.append(f"\n<b>— {schedule.fmt_date(current_day)} —</b>")
        parts.append(
            f"🕐 <b>{schedule.fmt_period(b.starts_at, b.duration)}</b> · {b.service_title} · "
            f"{b.price} р.\n    💇 {b.master_name} · 👤 {escape(b.name)}, {b.phone}  <i>#{b.id}</i>"
        )
    total = sum(b.price for b in bookings)
    parts.append(f"\nИтого: <b>{len(bookings)}</b> зап. на <b>{total} р.</b>")
    parts.append("\n<i>Нажмите на запись ниже, чтобы отменить её.</i>")
    text = "\n".join(parts)
    return text if len(text) < 4000 else text[:3990] + "…"


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    start, end, _ = day_range(0)
    today = database.between(start, end)
    start, end, _ = day_range(1)
    tomorrow = database.between(start, end)
    await message.answer(
        "🛠 <b>Панель администратора</b>\n\n"
        f"Записей сегодня: <b>{len(today)}</b>\n"
        f"Записей завтра: <b>{len(tomorrow)}</b>\n\n"
        "Новые записи и отмены приходят сюда автоматически.",
        reply_markup=kb.admin_menu(),
    )


@router.callback_query(AdminDayCb.filter())
async def cb_admin_day(cb: CallbackQuery, callback_data: AdminDayCb):
    start, end, title = day_range(callback_data.days)
    bookings = database.between(start, end)
    await cb.message.edit_text(render_bookings(title, bookings),
                               reply_markup=kb.admin_bookings(bookings))
    await cb.answer()


@router.callback_query(AdminCancelCb.filter())
async def cb_admin_cancel(cb: CallbackQuery, callback_data: AdminCancelCb):
    b = database.get(callback_data.id)
    if not b or b.status != "active":
        await cb.answer("Запись уже отменена", show_alert=True)
        return
    database.cancel(b.id)
    await cb.answer(f"Запись #{b.id} отменена")
    await cb.message.edit_text(
        f"❌ Запись #{b.id} отменена, клиент получил уведомление.\n\n"
        f"{b.service_title} · мастер {b.master_name} · "
        f"{schedule.fmt_date(b.starts_at.date())}, {b.starts_at:%H:%M}\n"
        f"👤 {escape(b.name)}, {b.phone}",
        reply_markup=kb.admin_menu(),
    )
    try:
        await cb.bot.send_message(
            b.user_id,
            "😔 <b>Ваша запись отменена салоном</b>\n\n"
            f"{b.service_title}\n"
            f"📅 {schedule.fmt_date(b.starts_at.date())}, {b.starts_at:%H:%M}\n\n"
            f"Приносим извинения! Выберите другое время через /book "
            f"или позвоните нам: {config.SALON['phone']}",
        )
    except Exception:
        pass
