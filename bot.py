"""Точка входа: python bot.py"""

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

import config
import database
from handlers import admin, client
from notifications import reminder_loop


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    if not config.BOT_TOKEN or ":" not in config.BOT_TOKEN:
        print("Не указан BOT_TOKEN. Откройте файл .env и вставьте токен от @BotFather.")
        sys.exit(1)
    if not config.ADMIN_IDS:
        logging.warning("ADMIN_IDS не задан — уведомления о записях никому не придут. "
                        "Отправьте боту /myid и впишите число в .env")

    database.init()
    bot = Bot(config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_routers(admin.router, client.router)  # admin первым: у client есть общий fallback

    await bot.set_my_commands([
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="book", description="Записаться"),
        BotCommand(command="cancel", description="Отменить текущее действие"),
    ])

    reminders = asyncio.create_task(reminder_loop(bot))
    me = await bot.get_me()
    logging.info("Бот @%s запущен. Остановить: Ctrl+C", me.username)
    try:
        await dp.start_polling(bot)
    finally:
        reminders.cancel()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
