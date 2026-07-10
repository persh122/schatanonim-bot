"""
Конфигурация бота.
Токен и список администраторов берутся из переменных окружения.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Основные настройки ──────────────────────────────────────────────────────
BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]

# ID администраторов (через запятую в .env, например: ADMIN_IDS=123456,789012)
_admin_ids_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: list[int] = (
    [int(x.strip()) for x in _admin_ids_raw.split(",") if x.strip()]
    if _admin_ids_raw
    else []
)

# ── VIP через Telegram Stars ─────────────────────────────────────────────────
VIP_PRICE_STARS: int = 100        # цена VIP в звёздах (XTR)
VIP_DURATION_DAYS: int = 30       # срок действия VIP в днях

# ── Реклама для не-VIP ───────────────────────────────────────────────────────
# Рекламное сообщение отправляется каждые N сообщений
AD_INTERVAL: int = 20
AD_TEXT: str = (
    "💎 <b>Надоела реклама?</b> Купи VIP и забудь о ней навсегда!\n"
    "Нажми /vip чтобы узнать подробности."
)

# ── База данных ──────────────────────────────────────────────────────────────
DB_PATH: str = os.getenv("DB_PATH", "bot/data/bot.db")
