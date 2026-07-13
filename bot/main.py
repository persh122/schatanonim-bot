"""
Точка входа Telegram-бота Schatanonim.

Запуск:
    cd bot
    pip install -r requirements.txt
    python main.py

Режимы:
    - Replit (REPLIT_DEV_DOMAIN задан)  → webhook через API-сервер на localhost:5000
    - Railway / локально               → long-polling
"""

import asyncio
import logging
import sys
import os
import traceback

# Добавляем папку bot/ в sys.path, чтобы импорты работали корректно
sys.path.insert(0, os.path.dirname(__file__))

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent

from config import BOT_TOKEN, ADMIN_IDS
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

# ── Константы ─────────────────────────────────────────────────────────────────
WEBHOOK_INTERNAL_PORT = 5000   # слушаем только на localhost, API-сервер проксирует


# ── Вспомогательные функции ───────────────────────────────────────────────────

def _format_user_count(n: int) -> str:
    return f"{n:,}".replace(",", " ")


async def update_description_loop(bot: Bot) -> None:
    """Устанавливает описание бота один раз при запуске."""
    try:
        await bot.set_my_short_description("🔥 Анонимный чат для знакомств 1 на 1")
        await bot.set_my_description("🔥 Анонимный чат для знакомств 1 на 1")
    except Exception as e:
        logger.warning(f"Не удалось обновить описание: {e}")


# ── Главная функция ───────────────────────────────────────────────────────────

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

    # Подключаем middleware (антиспам)
    dp.message.middleware(ThrottlingMiddleware(rate_limit=0.5))

    # Глобальный обработчик ошибок
    @dp.errors()
    async def global_error_handler(event: ErrorEvent) -> bool:
        logger.exception(f"Необработанная ошибка: {event.exception}")
        tb = traceback.format_exc()
        text = f"⚠️ <b>Ошибка бота</b>\n<pre>{tb[-3000:]}</pre>"

        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, text, parse_mode="HTML")
            except Exception:
                pass

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
                    f"❌ Внутренняя ошибка. Сообщите разработчику:\n<pre>{str(event.exception)[:500]}</pre>",
                    parse_mode="HTML",
                )
        except Exception:
            pass

        return True

    # Регистрируем роутеры (порядок важен!)
    dp.include_router(admin.router)
    dp.include_router(vip.router)
    dp.include_router(start.router)
    dp.include_router(search.router)
    dp.include_router(report.router)
    dp.include_router(chat.router)

    # Запускаем описание в фоне
    asyncio.create_task(update_description_loop(bot))

    domain = os.getenv("REPLIT_DEV_DOMAIN", "")

    if domain:
        # ── WEBHOOK режим (Replit) ────────────────────────────────────────────
        # Telegram сам делает POST-запросы → repl не засыпает 24/7 бесплатно
        from aiohttp import web
        from aiogram.webhook.aiohttp_server import SimpleRequestHandler

        webhook_url = f"https://{domain}/api/telegram-webhook"
        await bot.set_webhook(webhook_url, drop_pending_updates=False)
        logger.info(f"✅ Webhook установлен: {webhook_url}")

        # Запускаем aiohttp-сервер на localhost:5000 (API-сервер проксирует)
        aio_app = web.Application()
        SimpleRequestHandler(dispatcher=dp, bot=bot).register(aio_app, path="/")

        runner = web.AppRunner(aio_app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", WEBHOOK_INTERNAL_PORT)
        await site.start()
        logger.info(f"✅ Webhook-сервер запущен на 127.0.0.1:{WEBHOOK_INTERNAL_PORT}")

        # Держим event loop активным
        await asyncio.Event().wait()

    else:
        # ── POLLING режим (Railway / локально) ───────────────────────────────
        await bot.delete_webhook(drop_pending_updates=False)
        logger.info("Бот запускается в режиме polling…")
        try:
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        finally:
            await bot.session.close()
            logger.info("Бот остановлен.")


if __name__ == "__main__":
    asyncio.run(main())
