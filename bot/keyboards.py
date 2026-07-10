"""
Все клавиатуры бота.
"""

from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


# ── Главное меню ─────────────────────────────────────────────────────────────

def main_menu(is_vip: bool = False) -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.button(text="🔎 Найти собеседника")
    kb.button(text="🔗 Моя ссылка")
    kb.button(text="📊 Статистика")
    kb.button(text="👤 Мой профиль")
    if not is_vip:
        kb.button(text="💎 Купить VIP")
    kb.button(text="ℹ️ Помощь")
    kb.adjust(2, 2, 1)
    return kb.as_markup(resize_keyboard=True)


# ── Клавиатура в чате ────────────────────────────────────────────────────────

def chat_keyboard() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.button(text="⏭ Следующий")
    kb.button(text="❌ Завершить чат")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)


# ── Кнопка «Остановить поиск» ────────────────────────────────────────────────

def cancel_search_keyboard() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.button(text="🚫 Остановить поиск")
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True)


# ── Убрать клавиатуру ────────────────────────────────────────────────────────

def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


# ── Анонимные сообщения ──────────────────────────────────────────────────────

def anon_message_keyboard(token: str) -> InlineKeyboardMarkup:
    """Кнопки под входящим анонимным сообщением."""
    builder = InlineKeyboardBuilder()
    builder.button(text="↩️ Ответить",         callback_data=f"anon_reply:{token}")
    builder.button(text="🚫 Заблокировать",    callback_data=f"anon_block:{token}")
    builder.adjust(2)
    return builder.as_markup()


def cancel_anon_keyboard() -> ReplyKeyboardMarkup:
    """Кнопка отмены при вводе анонимного сообщения."""
    kb = ReplyKeyboardBuilder()
    kb.button(text="❌ Отмена")
    return kb.as_markup(resize_keyboard=True, one_time_keyboard=True)


# ── Выбор пола (для VIP) ─────────────────────────────────────────────────────

def gender_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👨 Мужской", callback_data="gender:male")
    builder.button(text="👩 Женский", callback_data="gender:female")
    builder.button(text="🌈 Любой",   callback_data="gender:any")
    builder.adjust(2, 1)
    return builder.as_markup()


def gender_pref_keyboard() -> InlineKeyboardMarkup:
    """Предпочтение по полу собеседника (VIP-функция)."""
    builder = InlineKeyboardBuilder()
    builder.button(text="👨 Парень",  callback_data="pref:male")
    builder.button(text="👩 Девушка", callback_data="pref:female")
    builder.button(text="🎲 Случайно", callback_data="pref:any")
    builder.adjust(2, 1)
    return builder.as_markup()


# ── VIP-покупка ──────────────────────────────────────────────────────────────

def vip_buy_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💎 Купить VIP за ⭐ Stars", callback_data="vip:buy")
    builder.button(text="❓ Что даёт VIP?",         callback_data="vip:info")
    builder.adjust(1)
    return builder.as_markup()


# ── Админ-панель ─────────────────────────────────────────────────────────────

def admin_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика",        callback_data="admin:stats")
    builder.button(text="🚫 Забанить пользователя",  callback_data="admin:ban")
    builder.button(text="✅ Разбанить пользователя", callback_data="admin:unban")
    builder.button(text="💎 Выдать VIP",        callback_data="admin:givevip")
    builder.button(text="📣 Рассылка",          callback_data="admin:broadcast")
    builder.button(text="👥 Список пользователей", callback_data="admin:users")
    builder.adjust(1)
    return builder.as_markup()
