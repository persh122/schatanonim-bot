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
import traceback
from asyncio import StreamReader, StreamWriter

# Добавляем папку bot/ в sys.path, чтобы импорты работали корректно
sys.path.insert(0, os.path.dirname(__file__))

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent

from config import BOT_TOKEN, ADMIN_IDS
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
    # В Replit dev порт 8080 занят API-сервером → берём 8081 как fallback
    port = int(os.getenv("HEALTH_PORT", os.getenv("PORT", "8081")))
    try:
        server = await asyncio.start_server(_handle_health, "0.0.0.0", port)
        logger.info(f"Health-check сервер запущен на порту {port}")
        async with server:
            await server.serve_forever()
    except OSError:
        logger.warning(f"Порт {port} занят — health-сервер не запущен (не критично)")


async def keep_alive_loop() -> None:
    """
    Пингует собственный Replit URL через интернет каждые 4 минуты.
    Входящий HTTP-запрос сбрасывает таймер сна Replit → бот работает 24/7 бесплатно.
    На Railway эта функция ничего не делает (REPLIT_DEV_DOMAIN не установлен).
    """
    import aiohttp
    domain = os.getenv("REPLIT_DEV_DOMAIN", "")
    if not domain:
        return  # не Replit → выходим
    url = f"https://{domain}/api/healthz"
    logger.info(f"Keep-alive loop запущен → {url}")
    while True:
        await asyncio.sleep(4 * 60)  # каждые 4 минуты
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    logger.debug(f"Keep-alive ping: HTTP {resp.status}")
        except Exception as e:
            logger.debug(f"Keep-alive ping failed (not critical): {e}")


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

    # Глобальный обработчик ошибок — логирует и шлёт traceback пользователю и админам
    @dp.errors()
    async def global_error_handler(event: ErrorEvent) -> bool:
        logger.exception(f"Необработанная ошибка: {event.exception}")
        tb = traceback.format_exc()
        text = f"⚠️ <b>Ошибка бота</b>\n<pre>{tb[-3000:]}</pre>"

        # Отправляем ошибку администраторам
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, text, parse_mode="HTML")
            except Exception:
                pass

        # Отправляем ошибку пользователю, вызвавшему команду
        try:
            upd = event.update
            chat_id = None
            if upd.message:
                chat_id = upd.message.chat.id
            elif upd.callback_query:
                chat_id = upd.callback_query.message.chat.id
            if chat_id:
                await bot.send_message(
                    chat_id,
                    f"❌ Внутренняя ошибка бота. Сообщите разработчику:\n<pre>{str(event.exception)[:500]}</pre>",
                    parse_mode="HTML",
                )
        except Exception:
            pass

        return True

    # Регистрируем роутеры (порядок важен!)
    dp.include_router(admin.router)    # Админ — первый (приоритет)
    dp.include_router(vip.router)      # VIP-покупка и платёж
    dp.include_router(start.router)    # /start, /help, профиль
    dp.include_router(search.router)   # Поиск и очередь
    dp.include_router(report.router)   # Жалобы на собеседника
    dp.include_router(chat.router)     # Сообщения в чате (последний!)

    # Удаляем вебхук (без сброса апдейтов — не теряем сообщения при краше)
    await bot.delete_webhook(drop_pending_updates=False)

    # Запускаем HTTP health-check сервер (нужен для Replit deployment)
    asyncio.create_task(start_health_server())

    # Само-пинг: бот пингует свой Replit URL → не засыпает 24/7 бесплатно
    asyncio.create_task(keep_alive_loop())

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
