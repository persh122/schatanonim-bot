"""
Обработчики VIP-покупки через Telegram Stars.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.filters import Command

import database as db
import keyboards as kb
from config import VIP_PRICE_STARS, VIP_DURATION_DAYS

router = Router()


@router.message(Command("vip"))
@router.message(F.text == "💎 Купить VIP")
async def cmd_vip(message: Message) -> None:
    vip = await db.is_vip(message.from_user.id)
    if vip:
        user_data = await db.get_user(message.from_user.id)
        until = user_data.get("vip_until", "")[:10] if user_data else "—"
        await message.answer(
            f"💎 У вас уже есть <b>VIP</b>!\n\nДействует до: <code>{until}</code>",
            parse_mode="HTML",
        )
        return

    await message.answer(
        f"💎 <b>VIP-статус</b>\n\n"
        f"Стоимость: <b>{VIP_PRICE_STARS} ⭐ Telegram Stars</b>\n"
        f"Срок: <b>{VIP_DURATION_DAYS} дней</b>\n\n"
        "<b>VIP даёт:</b>\n"
        "✅ Выбор пола собеседника\n"
        "✅ Приоритет в очереди поиска\n"
        "✅ Без рекламы\n"
        "✅ Фильтрация по полу\n"
        "✅ Значок 💎 в чатах\n\n"
        "Нажми кнопку ниже для покупки:",
        reply_markup=kb.vip_buy_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "vip:info")
async def cb_vip_info(call: CallbackQuery) -> None:
    await call.answer(
        "VIP: нет рекламы, выбор пола, приоритет в поиске.",
        show_alert=True,
    )


@router.callback_query(F.data == "vip:buy")
async def cb_vip_buy(call: CallbackQuery) -> None:
    """Отправляет счёт через Telegram Stars (XTR)."""
    await call.answer()

    if await db.is_vip(call.from_user.id):
        await call.message.answer("💎 У вас уже есть VIP!")
        return

    await call.message.answer_invoice(
        title=f"💎 VIP на {VIP_DURATION_DAYS} дней",
        description=(
            f"Получите VIP-статус на {VIP_DURATION_DAYS} дней:\n"
            "• Выбор пола собеседника\n"
            "• Приоритет в поиске\n"
            "• Без рекламы"
        ),
        payload="vip_purchase",
        currency="XTR",                           # Telegram Stars
        prices=[LabeledPrice(label="VIP", amount=VIP_PRICE_STARS)],
        protect_content=False,
    )


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    """Telegram требует ответа в течение 10 секунд."""
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message) -> None:
    """Обрабатываем успешную оплату звёздами."""
    payment = message.successful_payment
    user_id = message.from_user.id

    await db.grant_vip(
        user_id=user_id,
        days=VIP_DURATION_DAYS,
        telegram_charge=payment.telegram_payment_charge_id,
        stars=payment.total_amount,
    )

    await message.answer(
        f"🎉 <b>Спасибо!</b> VIP-статус активирован на <b>{VIP_DURATION_DAYS} дней</b>.\n\n"
        "Теперь вам доступны:\n"
        "💎 Выбор пола собеседника при поиске\n"
        "🚀 Приоритет в очереди\n"
        "🚫 Без рекламы",
        reply_markup=kb.main_menu(is_vip=True),
        parse_mode="HTML",
    )


@router.message(Command("gender"))
async def cmd_gender(message: Message) -> None:
    """Позволяет указать свой пол (нужно для VIP-фильтрации)."""
    await message.answer(
        "👤 Укажите свой пол (используется для фильтрации VIP-пользователей):",
        reply_markup=kb.gender_keyboard(),
    )


@router.callback_query(F.data.startswith("gender:"))
async def cb_set_gender(call: CallbackQuery) -> None:
    gender = call.data.split(":")[1]
    await db.set_gender(call.from_user.id, gender)

    labels = {"male": "👨 Мужской", "female": "👩 Женский"}
    label = labels.get(gender, gender)
    await call.message.edit_text(
        f"✅ Вы успешно сменили пол на: <b>{label}</b>",
        parse_mode="HTML",
    )
    await call.answer()
