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
    kb.button(text="🔥 Флирт чат")
    kb.button(text="🚻 Поиск по полу")
    kb.button(text="👤 Мой профиль")
    if not is_vip:
        kb.button(text="💎 Купить VIP")
    kb.adjust(2, 1, 2)
    return kb.as_markup(resize_keyboard=True)


# ── Клавиатура в чате ────────────────────────────────────────────────────────

def chat_keyboard() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.button(text="⏭ Следующий")
    kb.button(text="❌ Завершить чат")
    kb.button(text="🚨 Пожаловаться")
    kb.button(text="🏠 Главное меню")
    kb.adjust(2, 1, 1)
    return kb.as_markup(resize_keyboard=True)


# ── Кнопка «Остановить поиск» ────────────────────────────────────────────────

def cancel_search_keyboard() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.button(text="🚫 Остановить поиск")
    kb.button(text="🏠 Главное меню")
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True)


# ── Убрать клавиатуру ────────────────────────────────────────────────────────

def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


# ── Оценка собеседника ───────────────────────────────────────────────────────

def rating_keyboard(partner_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👍",        callback_data=f"rate:{partner_id}:1")
    builder.button(text="👎",        callback_data=f"rate:{partner_id}:0")
    builder.button(text="Пропустить", callback_data="rate:skip")
    builder.adjust(2, 1)
    return builder.as_markup()


# ── Выбор пола при регистрации ───────────────────────────────────────────────

def reg_gender_keyboard() -> InlineKeyboardMarkup:
    """Выбор пола при регистрации — только мужской или женский."""
    builder = InlineKeyboardBuilder()
    builder.button(text="👨 Мужской", callback_data="reg_gender:male")
    builder.button(text="👩 Женский", callback_data="reg_gender:female")
    builder.adjust(2)
    return builder.as_markup()


# ── Выбор пола (смена в профиле) ─────────────────────────────────────────────

def gender_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👨 Мужской", callback_data="gender:male")
    builder.button(text="👩 Женский", callback_data="gender:female")
    builder.adjust(2)
    return builder.as_markup()


def gender_pref_keyboard(mode: str = "normal") -> InlineKeyboardMarkup:
    """Предпочтение по полу собеседника (VIP-функция). mode: 'normal'|'flirt'."""
    builder = InlineKeyboardBuilder()
    builder.button(text="👨 Парень",   callback_data=f"pref:male:{mode}")
    builder.button(text="👩 Девушка",  callback_data=f"pref:female:{mode}")
    builder.button(text="🎲 Случайно", callback_data=f"pref:any:{mode}")
    builder.adjust(2, 1)
    return builder.as_markup()


# ── VIP-покупка ──────────────────────────────────────────────────────────────

def vip_buy_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="3 дня — 13 ⭐",  callback_data="vip:buy:3:13")
    builder.button(text="7 дней — 25 ⭐", callback_data="vip:buy:7:25")
    builder.button(text="30 дней — 100 ⭐", callback_data="vip:buy:30:100")
    builder.button(text="❓ Что даёт VIP?", callback_data="vip:info")
    builder.adjust(1)
    return builder.as_markup()


# ── Админ-панель ─────────────────────────────────────────────────────────────

def active_chats_keyboard(chats: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if not chats:
        builder.button(text="Активных чатов нет", callback_data="admin:noop")
    else:
        for c in chats:
            g1 = {"male": "👨", "female": "👩"}.get(c.get("u1_gender", ""), "👤")
            g2 = {"male": "👨", "female": "👩"}.get(c.get("u2_gender", ""), "👤")
            a1 = c.get("u1_age") or "?"
            a2 = c.get("u2_age") or "?"
            label = f"{g1}{a1} ↔ {g2}{a2}"
            builder.button(
                text=label,
                callback_data=f"admin:joinchat:{c['user1_id']}:{c['user2_id']}",
            )
    builder.button(text="◀️ Назад", callback_data="admin:back")
    builder.adjust(1)
    return builder.as_markup()


def admin_in_chat_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🚪 Выйти из чата", callback_data="admin:leavechat")
    return builder.as_markup()


def admin_keyboard(spy_on: bool = False) -> InlineKeyboardMarkup:
    spy_label = "👁 Наблюдение: ВКЛ 🟢" if spy_on else "👁 Наблюдение: ВЫКЛ 🔴"
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика",             callback_data="admin:stats")
    builder.button(text="🚨 Жалобы",                 callback_data="admin:reports")
    builder.button(text="💬 Активные чаты",          callback_data="admin:active_chats")
    builder.button(text=spy_label,                   callback_data="admin:spy")
    builder.button(text="🚫 Забанить пользователя",  callback_data="admin:ban")
    builder.button(text="✅ Разбанить пользователя", callback_data="admin:unban")
    builder.button(text="💎 Выдать VIP",             callback_data="admin:givevip")
    builder.button(text="📣 Рассылка",               callback_data="admin:broadcast")
    builder.button(text="👥 Список пользователей",   callback_data="admin:users")
    builder.adjust(1)
    return builder.as_markup()
