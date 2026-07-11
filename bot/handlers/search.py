"""
Обработчики поиска собеседника и управления очередью.
Поддерживает два режима: 'normal' (обычный) и 'flirt' (флирт).
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

import database as db
import keyboards as kb

router = Router()


# ── Внутренняя логика поиска ─────────────────────────────────────────────────

async def _do_search(
    bot, user_id: int, gender_pref: str, own_gender: str,
    vip: bool, chat_mode: str = "normal"
) -> None:
    """Атомарно ищет пару или добавляет в очередь."""
    partner_id = await db.find_and_claim_partner(
        user_id, gender_pref, own_gender, vip, chat_mode
    )

    if partner_id:
        # Загружаем профили обоих участников
        user_data    = await db.get_user(user_id)
        partner_data = await db.get_user(partner_id)

        def profile_line(d: dict | None) -> str:
            if not d:
                return ""
            g = {"male": "👨 Парень", "female": "👩 Девушка"}.get(d.get("gender", ""), "")
            a = str(d.get("age") or "") 
            parts = [p for p in [g, a] if p]
            return (", ".join(parts) + "\n") if parts else ""

        mode_emoji = "🔥" if chat_mode == "flirt" else "✅"
        mode_hint  = "Это флирт-чат 🔥\n" if chat_mode == "flirt" else ""

        msg_to_user = (
            f"{mode_emoji} <b>Собеседник найден!</b>\n"
            f"{mode_hint}"
            f"Собеседник: {profile_line(partner_data)}"
            "Используйте кнопки ниже для управления чатом."
        )
        msg_to_partner = (
            f"{mode_emoji} <b>Собеседник найден!</b>\n"
            f"{mode_hint}"
            f"Собеседник: {profile_line(user_data)}"
            "Используйте кнопки ниже для управления чатом."
        )
        await bot.send_message(user_id,    msg_to_user,    reply_markup=kb.chat_keyboard(), parse_mode="HTML")
        await bot.send_message(partner_id, msg_to_partner, reply_markup=kb.chat_keyboard(), parse_mode="HTML")
    else:
        await db.add_to_queue(user_id, gender_pref, own_gender, vip, chat_mode)
        q_len = await db.queue_length()
        icon = "🔥" if chat_mode == "flirt" else "🔎"
        label = "флирт-собеседника" if chat_mode == "flirt" else "собеседника"
        await bot.send_message(
            user_id,
            f"{icon} <b>Ищем {label}…</b>\n\n"
            f"В очереди: {q_len} чел.\n\n"
            "Мы уведомим тебя, когда найдём пару.",
            reply_markup=kb.cancel_search_keyboard(),
            parse_mode="HTML",
        )


async def _pre_search_checks(message: Message) -> bool:
    """Проверяет регистрацию, бан, активный чат, очередь. False = прерваться."""
    user_id = message.from_user.id

    if not await db.is_registered(user_id):
        await message.answer(
            "⚠️ Сначала пройди регистрацию — нажми /start",
        )
        return False

    if await db.is_banned(user_id):
        await message.answer("🚫 Вы заблокированы.")
        return False

    if await db.is_in_chat(user_id):
        await message.answer(
            "Вы уже в чате! Завершите его, чтобы найти нового собеседника.",
            reply_markup=kb.chat_keyboard(),
        )
        return False

    if await db.is_in_queue(user_id):
        await message.answer(
            "🔎 Вы уже в очереди поиска…",
            reply_markup=kb.cancel_search_keyboard(),
        )
        return False

    return True


# ── Обычный поиск ────────────────────────────────────────────────────────────

@router.message(F.text == "🔎 Найти собеседника")
async def btn_search(message: Message) -> None:
    if not await _pre_search_checks(message):
        return

    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    if not user_data:
        await message.answer("Пожалуйста, напиши /start сначала.")
        return

    vip = await db.is_vip(user_id)
    own_gender = user_data.get("gender", "any")

    if vip:
        await message.answer(
            "💎 <b>VIP-поиск</b>\n\nКого ищем?",
            reply_markup=kb.gender_pref_keyboard(mode="normal"),
            parse_mode="HTML",
        )
    else:
        await _do_search(message.bot, user_id, "any", own_gender, False, "normal")


# ── Поиск по полу (только VIP) ───────────────────────────────────────────────

@router.message(F.text == "🚻 Поиск по полу")
async def btn_gender_search(message: Message) -> None:
    if not await _pre_search_checks(message):
        return

    user_id = message.from_user.id
    vip = await db.is_vip(user_id)

    if not vip:
        await message.answer(
            "💎 <b>Поиск по полу — только для VIP</b>\n\n"
            "Купи VIP чтобы выбирать пол собеседника.\n"
            "Нажми /vip чтобы узнать тарифы.",
            parse_mode="HTML",
        )
        return

    await message.answer(
        "💎 <b>Поиск по полу</b>\n\nКого ищем?",
        reply_markup=kb.gender_pref_keyboard(mode="normal"),
        parse_mode="HTML",
    )


# ── Флирт-поиск ──────────────────────────────────────────────────────────────

@router.message(F.text == "🔥 Флирт чат")
async def btn_flirt(message: Message) -> None:
    if not await _pre_search_checks(message):
        return

    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    if not user_data:
        await message.answer("Пожалуйста, напиши /start сначала.")
        return

    vip = await db.is_vip(user_id)
    own_gender = user_data.get("gender", "any")

    if vip:
        await message.answer(
            "🔥 <b>Флирт-поиск</b>\n\nКого ищем?",
            reply_markup=kb.gender_pref_keyboard(mode="flirt"),
            parse_mode="HTML",
        )
    else:
        await _do_search(message.bot, user_id, "any", own_gender, False, "flirt")


# ── VIP выбрал пол (для обоих режимов) ───────────────────────────────────────

@router.callback_query(F.data.startswith("pref:"))
async def cb_gender_pref(call: CallbackQuery) -> None:
    """Формат: pref:{gender}:{mode}  (напр. pref:female:flirt)"""
    user_id = call.from_user.id

    # Серверная проверка VIP
    vip = await db.is_vip(user_id)
    if not vip:
        await call.answer("💎 Эта функция доступна только VIP!", show_alert=True)
        await call.message.edit_reply_markup(reply_markup=None)
        return

    parts = call.data.split(":")
    gender_pref = parts[1]                       # male | female | any
    chat_mode   = parts[2] if len(parts) > 2 else "normal"

    user_data = await db.get_user(user_id)
    own_gender = user_data.get("gender", "any") if user_data else "any"

    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer()
    await _do_search(call.message.bot, user_id, gender_pref, own_gender, True, chat_mode)


# ── Остановить поиск ─────────────────────────────────────────────────────────

@router.message(F.text == "🚫 Остановить поиск")
async def btn_cancel_search(message: Message) -> None:
    user_id = message.from_user.id
    if await db.is_in_queue(user_id):
        await db.remove_from_queue(user_id)
        vip = await db.is_vip(user_id)
        await message.answer("🚫 Поиск остановлен.", reply_markup=kb.main_menu(is_vip=vip))
    else:
        vip = await db.is_vip(user_id)
        await message.answer("Вы не в очереди.", reply_markup=kb.main_menu(is_vip=vip))
