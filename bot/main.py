"""
Точка входа Telegram-бота Schatanonim.

Запуск:
    cd bot
    pip install -r requirements.txt
    python main.py
"""

import asyncio
import logging
import sys
import os

# Добавляем папку bot/ в sys.path, чтобы импорты работали корректно
sys.path.insert(0, os.path.dirname(__file__))

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import init_db
from middlewares.throttling import ThrottlingMiddleware

# Импортируем роутеры хендлеров
from handlers import start, search, chat, vip, admin, report

# ── Логирование ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ── Запуск ───────────────────────────────────────────────────────────────────

async def main() -> None:
    logger.info("Инициализация базы данных…")
    await init_db()
    logger.info("База данных готова.")

    # Создаём бота и диспетчер
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Подключаем middleware (антиспам: не чаще 1 сообщения в 0.5 с)
    dp.message.middleware(ThrottlingMiddleware(rate_limit=0.5))

    # Регистрируем роутеры (порядок важен!)
    dp.include_router(admin.router)    # Админ — первый (приоритет)
    dp.include_router(vip.router)      # VIP-покупка и платёж
    dp.include_router(start.router)    # /start, /help, профиль
    dp.include_router(search.router)   # Поиск и очередь
    dp.include_router(report.router)   # Жалобы на собеседника
    dp.include_router(chat.router)     # Сообщения в чате (последний!)

    # Удаляем старые апдейты при старте
    await bot.delete_webhook(drop_pending_updates=True)

    logger.info("Бот запускается… (polling)")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        logger.info("Бот остановлен.")


if __name__ == "__main__":
    asyncio.run(main())
