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
from asyncio import StreamReader, StreamWriter

# Добавляем папку bot/ в sys.path, чтобы импорты работали корректно
sys.path.insert(0, os.path.dirname(__file__))

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import init_db, get_user_count
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

def _format_user_count(n: int) -> str:
    """Форматирует число с пробелами как разделителями тысяч (123 456)."""
    return f"{n:,}".replace(",", " ")


async def _handle_health(reader: StreamReader, writer: StreamWriter) -> None:
    """Минимальный HTTP-ответ для health-check Replit."""
    await reader.read(1024)  # читаем запрос (не используем)
    writer.write(
        b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 2\r\n\r\nOK"
    )
    await writer.drain()
    writer.close()


async def start_health_server() -> None:
    """Запускает HTTP-сервер на PORT (для Replit deployment health-check)."""
    port = int(os.getenv("PORT", "8080"))
    server = await asyncio.start_server(_handle_health, "0.0.0.0", port)
    logger.info(f"Health-check сервер запущен на порту {port}")
    async with server:
        await server.serve_forever()


async def update_description_loop(bot: Bot) -> None:
    """Устанавливает описание бота один раз при запуске."""
    try:
        await bot.set_my_short_description("🔥 Анонимный чат для знакомств 1 на 1")
        await bot.set_my_description("🔥 Анонимный чат для знакомств 1 на 1")
    except Exception as e:
        logger.warning(f"Не удалось обновить описание: {e}")


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

    # Запускаем HTTP health-check сервер (нужен для Replit deployment)
    asyncio.create_task(start_health_server())

    # Запускаем фоновое обновление описания
    asyncio.create_task(update_description_loop(bot))

    logger.info("Бот запускается… (polling)")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        logger.info("Бот остановлен.")


if __name__ == "__main__":
    asyncio.run(main())
