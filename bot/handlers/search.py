"""
Обработчики поиска собеседника и управления очередью.
"""

import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import database as db
import keyboards as kb

router = Router()


async def _do_search(bot, user_id: int, gender_pref: str, own_gender: str, vip: bool) -> None:
    """Внутренняя логика: атомарно ищет пару или добавляет в очередь."""
    # Атомарная операция: поиск + удаление из очереди + создание чата в одной транзакции
    partner_id = await db.find_and_claim_partner(user_id, gender_pref, own_gender, vip)

    if partner_id:
        # Нашли пару — чат уже создан внутри find_and_claim_partner
        await bot.send_message(
            user_id,
            "✅ <b>Собеседник найден!</b>\n\n"
            "Можете начинать общение. Ваш собеседник не знает, кто вы.\n"
            "Используйте кнопки ниже для управления чатом.",
            reply_markup=kb.chat_keyboard(),
            parse_mode="HTML",
        )
        await bot.send_message(
            partner_id,
            "✅ <b>Собеседник найден!</b>\n\n"
            "Можете начинать общение. Ваш собеседник не знает, кто вы.\n"
            "Используйте кнопки ниже для управления чатом.",
            reply_markup=kb.chat_keyboard(),
            parse_mode="HTML",
        )
    else:
        # Добавляем в очередь и ждём
        await db.add_to_queue(user_id, gender_pref, own_gender, vip)
        q_len = await db.queue_length()
        await bot.send_message(
            user_id,
            f"🔎 <b>Ищем собеседника…</b>\n\n"
            f"В очереди: {q_len} чел.\n\n"
            "Мы уведомим тебя, когда найдём пару.",
            reply_markup=kb.cancel_search_keyboard(),
            parse_mode="HTML",
        )


@router.message(F.text == "🔎 Найти собеседника")
async def btn_search(message: Message) -> None:
    user_id = message.from_user.id

    # Проверки
    if await db.is_banned(user_id):
        await message.answer("🚫 Вы заблокированы.")
        return

    if await db.is_in_chat(user_id):
        await message.answer(
            "Вы уже в чате! Завершите текущий разговор, чтобы найти нового собеседника.",
            reply_markup=kb.chat_keyboard(),
        )
        return

    if await db.is_in_queue(user_id):
        await message.answer(
            "🔎 Вы уже в очереди поиска…",
            reply_markup=kb.cancel_search_keyboard(),
        )
        return

    user_data = await db.get_user(user_id)
    if not user_data:
        await message.answer("Пожалуйста, напиши /start сначала.")
        return

    vip = await db.is_vip(user_id)
    own_gender = user_data.get("gender", "any")

    # VIP может выбрать пол собеседника
    if vip:
        await message.answer(
            "💎 <b>VIP-поиск</b>\n\nКого ищем?",
            reply_markup=kb.gender_pref_keyboard(),
            parse_mode="HTML",
        )
    else:
        await _do_search(message.bot, user_id, "any", own_gender, False)


@router.callback_query(F.data.startswith("pref:"))
async def cb_gender_pref(call: CallbackQuery) -> None:
    """VIP выбрал предпочтение пола. Проверяем VIP-статус на сервере."""
    user_id = call.from_user.id

    # Серверная проверка VIP — callback data не является доверенным источником
    vip = await db.is_vip(user_id)
    if not vip:
        await call.answer("💎 Эта функция доступна только VIP!", show_alert=True)
        await call.message.edit_reply_markup(reply_markup=None)
        return

    await call.answer()
    gender_pref = call.data.split(":")[1]  # 'male' | 'female' | 'any'

    user_data = await db.get_user(user_id)
    own_gender = user_data.get("gender", "any") if user_data else "any"

    await call.message.edit_reply_markup(reply_markup=None)
    await _do_search(call.message.bot, user_id, gender_pref, own_gender, True)


@router.message(F.text == "🚫 Остановить поиск")
async def btn_cancel_search(message: Message) -> None:
    user_id = message.from_user.id
    if await db.is_in_queue(user_id):
        await db.remove_from_queue(user_id)
        vip = await db.is_vip(user_id)
        await message.answer(
            "🚫 Поиск остановлен.",
            reply_markup=kb.main_menu(is_vip=vip),
        )
    else:
        vip = await db.is_vip(user_id)
        await message.answer("Вы не в очереди.", reply_markup=kb.main_menu(is_vip=vip))
