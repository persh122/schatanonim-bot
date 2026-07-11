"""
Система жалоб: кнопка «🚨 Пожаловаться» в чате.
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
import keyboards as kb
from config import ADMIN_IDS

router = Router()

AUTO_BAN_THRESHOLD = 5   # жалоб → автобан


class ReportStates(StatesGroup):
    choosing_reason = State()


REASONS = [
    "Спам / реклама",
    "Оскорбления / агрессия",
    "Неприемлемый контент",
    "Мошенничество",
    "Другое",
]


@router.message(F.text == "🚨 Пожаловаться")
async def btn_report(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id

    partner_id = await db.get_partner(user_id)
    if not partner_id:
        await message.answer("⚠️ Вы не в чате — жаловаться не на кого.")
        return

    if await db.already_reported(user_id, partner_id):
        await message.answer("⚠️ Вы уже отправляли жалобу на этого собеседника.")
        return

    await state.update_data(reported_id=partner_id)
    await state.set_state(ReportStates.choosing_reason)

    from aiogram.utils.keyboard import ReplyKeyboardBuilder
    kb_reasons = ReplyKeyboardBuilder()
    for r in REASONS:
        kb_reasons.button(text=r)
    kb_reasons.button(text="❌ Отмена")
    kb_reasons.adjust(2)

    await message.answer(
        "🚨 <b>Жалоба на собеседника</b>\n\nВыберите причину:",
        reply_markup=kb_reasons.as_markup(resize_keyboard=True, one_time_keyboard=True),
        parse_mode="HTML",
    )


@router.message(ReportStates.choosing_reason)
async def process_report_reason(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    text = message.text or ""

    if text == "❌ Отмена":
        await state.clear()
        await message.answer("Жалоба отменена.", reply_markup=kb.chat_keyboard())
        return

    reason = text if text in REASONS else "Другое"
    data = await state.get_data()
    reported_id = data.get("reported_id")
    await state.clear()

    if not reported_id:
        await message.answer("❌ Ошибка. Попробуйте снова.", reply_markup=kb.chat_keyboard())
        return

    # Проверяем что собеседник ещё тот же
    current_partner = await db.get_partner(user_id)
    if current_partner != reported_id:
        await message.answer(
            "⚠️ Собеседник сменился — жалоба не отправлена.",
            reply_markup=kb.chat_keyboard(),
        )
        return

    total_reports = await db.add_report(user_id, reported_id, reason)

    await message.answer(
        "✅ <b>Жалоба принята.</b>\nСпасибо — модераторы проверят собеседника.",
        reply_markup=kb.chat_keyboard(),
        parse_mode="HTML",
    )

    # Уведомляем всех админов
    reporter_data = await db.get_user(user_id)
    reported_data = await db.get_user(reported_id)
    reporter_name = f"@{reporter_data['username']}" if reporter_data and reporter_data.get('username') else f"id:{user_id}"
    reported_name = f"@{reported_data['username']}" if reported_data and reported_data.get('username') else f"id:{reported_id}"

    alert = (
        f"🚨 <b>Новая жалоба</b>\n\n"
        f"От: {reporter_name} (<code>{user_id}</code>)\n"
        f"На: {reported_name} (<code>{reported_id}</code>)\n"
        f"Причина: <b>{reason}</b>\n"
        f"Всего жалоб на пользователя: <b>{total_reports}</b>"
    )

    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(admin_id, alert, parse_mode="HTML")
        except Exception:
            pass

    # Автобан при достижении порога
    if total_reports >= AUTO_BAN_THRESHOLD:
        await db.ban_user(reported_id)
        await db.end_chat(reported_id)
        await db.remove_from_queue(reported_id)
        try:
            await message.bot.send_message(
                reported_id,
                "🚫 Ваш аккаунт заблокирован за нарушение правил."
            )
        except Exception:
            pass
        for admin_id in ADMIN_IDS:
            try:
                await message.bot.send_message(
                    admin_id,
                    f"🤖 Автобан: пользователь <code>{reported_id}</code> "
                    f"заблокирован автоматически ({total_reports} жалоб).",
                    parse_mode="HTML",
                )
            except Exception:
                pass
