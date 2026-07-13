"""
Точка входа Telegram-бота Schatanonim (Railway deployment).
"""

import asyncio
import logging
import sys
import os
from asyncio import StreamReader, StreamWriter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramConflictError

from config import BOT_TOKEN
from database import init_db
from middlewares.throttling import ThrottlingMiddleware
from handlers import start, search, chat, vip, admin, report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


async def _handle_health(reader: StreamReader, writer: StreamWriter) -> None:
    await reader.read(1024)
    writer.write(
        b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 2\r\n\r\nOK"
    )
    await writer.drain()
    writer.close()


async def start_health_server() -> None:
    port = int(os.getenv("PORT", "8080"))
    try:
        server = await asyncio.start_server(_handle_health, "0.0.0.0", port)
        logger.info(f"Health-check сервер запущен на порту {port}")
        async with server:
            await server.serve_forever()
    except OSError:
        logger.warning(f"Порт {port} занят — health-сервер пропущен")


async def update_description(bot: Bot) -> None:
    try:
        await bot.set_my_short_description("🔥 Анонимный чат для знакомств 1 на 1")
        await bot.set_my_description("🔥 Анонимный чат для знакомств 1 на 1")
    except Exception as e:
        logger.warning(f"Не удалось обновить описание: {e}")


async def main() -> None:
    logger.info("Инициализация базы данных…")
    await init_db()
    logger.info("База данных готова.")

    asyncio.create_task(start_health_server())

    retry_delay = 10
    while True:
        bot = Bot(
            token=BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        dp = Dispatcher(storage=MemoryStorage())
        dp.message.middleware(ThrottlingMiddleware(rate_limit=0.5))
        dp.include_router(admin.router)
        dp.include_router(vip.router)
        dp.include_router(start.router)
        dp.include_router(search.router)
        dp.include_router(report.router)
        dp.include_router(chat.router)

        try:
            await bot.delete_webhook(drop_pending_updates=True)
            asyncio.create_task(update_description(bot))
            logger.info("Бот запускается… (polling)")
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
            break  # нормальная остановка
        except TelegramConflictError:
            logger.warning(
                f"Конфликт: другой экземпляр бота уже запущен. "
                f"Повтор через {retry_delay}с…"
            )
        except Exception as e:
            logger.error(f"Ошибка: {e}. Повтор через {retry_delay}с…")
        finally:
            await bot.session.close()

        await asyncio.sleep(retry_delay)
        retry_delay = min(retry_delay * 2, 120)


if __name__ == "__main__":
    import time
    while True:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            logger.info("Остановлен вручную.")
            break
        except Exception as e:
            logger.error(f"Критическая ошибка: {e}. Перезапуск через 15 сек...")
            time.sleep(15)
