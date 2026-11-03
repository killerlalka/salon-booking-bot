"""Уведомления администраторам и напоминания клиентам."""

import asyncio
import logging
from datetime import timedelta

from aiogram import Bot

import config
import database
import schedule


async def notify_admins(bot: Bot, text: str) -> None:
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            logging.exception("Не удалось отправить уведомление администратору %s", admin_id)


async def reminder_loop(bot: Bot) -> None:
    """Раз в минуту проверяет, кому пора напомнить о визите."""
    while True:
        try:
            now = schedule.now()
            until = now + timedelta(hours=config.REMIND_BEFORE_HOURS)
            for b in database.due_reminders(now, until):
                text = (
                    "⏰ <b>Напоминаем о записи</b>\n\n"
                    f"{b.service_title} · мастер {b.master_name}\n"
                    f"📅 Сегодня в {b.starts_at:%H:%M}\n"
                    f"📍 {config.SALON['address']}\n\n"
                    "Ждём вас! Если планы изменились — отмените запись в разделе «Мои записи»."
                )
                try:
                    await bot.send_message(b.user_id, text)
                except Exception:
                    logging.warning("Не удалось отправить напоминание по записи #%s", b.id)
                database.set_reminded(b.id)
        except Exception:
            logging.exception("Ошибка при отправке напоминаний")
        await asyncio.sleep(60)
