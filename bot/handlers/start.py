"""
Обработчик команды /start и регистрации пользователя.
"""

from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

import database as db
import keyboards as kb

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user = message.from_user
    is_new = await db.register_user(user.id, user.username, user.first_name)
    vip = await db.is_vip(user.id)

    if is_new:
        await message.answer(
            f"👋 Привет, <b>{user.first_name}</b>!\n\n"
            "Добро пожаловать в <b>Анонимный чат</b>.\n\n"
            "Здесь ты можешь анонимно общаться с случайными людьми.\n"
            "Никто не узнает, кто ты такой 🎭\n\n"
            "Нажми <b>🔎 Найти собеседника</b>, чтобы начать!",
            reply_markup=kb.main_menu(is_vip=vip),
            parse_mode="HTML",
        )
    else:
        await message.answer(
            "👋 С возвращением!\n\nНажми <b>🔎 Найти собеседника</b>, чтобы начать общение.",
            reply_markup=kb.main_menu(is_vip=vip),
            parse_mode="HTML",
        )


@router.message(Command("help"))
@router.message(lambda m: m.text == "ℹ️ Помощь")
async def cmd_help(message: Message) -> None:
    await message.answer(
        "📖 <b>Помощь</b>\n\n"
        "<b>Команды:</b>\n"
        "🔎 Найти собеседника — начать поиск\n"
        "⏭ Следующий — сменить собеседника\n"
        "❌ Завершить чат — выйти из чата\n\n"
        "<b>Что можно отправлять:</b>\n"
        "• Текст, фото, видео\n"
        "• Голосовые и видеосообщения\n"
        "• Стикеры и файлы\n\n"
        "<b>VIP-функции:</b> /vip\n\n"
        "🔒 Все чаты анонимны. Будь вежливым!",
        parse_mode="HTML",
    )


@router.message(Command("profile"))
@router.message(lambda m: m.text == "👤 Мой профиль")
async def cmd_profile(message: Message) -> None:
    user_data = await db.get_user(message.from_user.id)
    if not user_data:
        await message.answer("Сначала напиши /start")
        return

    vip_status = "💎 VIP" if user_data["is_vip"] else "👤 Обычный"
    vip_until = ""
    if user_data["is_vip"] and user_data["vip_until"]:
        vip_until = f"\nVIP до: <code>{user_data['vip_until'][:10]}</code>"

    gender_map = {"male": "👨 Мужской", "female": "👩 Женский", "any": "🌈 Не указан"}
    gender = gender_map.get(user_data["gender"], "🌈 Не указан")

    await message.answer(
        f"<b>Профиль</b>\n\n"
        f"ID: <code>{user_data['user_id']}</code>\n"
        f"Статус: {vip_status}{vip_until}\n"
        f"Пол: {gender}\n"
        f"Чатов: {user_data['total_chats']}\n"
        f"Сообщений: {user_data['messages_sent']}\n"
        f"Регистрация: {user_data['registered_at'][:10]}",
        parse_mode="HTML",
    )
