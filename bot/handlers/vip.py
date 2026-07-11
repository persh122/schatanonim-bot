"""
VIP-покупка через Telegram Stars — три тарифа.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.filters import Command

import database as db
import keyboards as kb

router = Router()

VIP_PLANS = {
    "3":  {"days": 3,  "stars": 13,  "label": "3 дня"},
    "7":  {"days": 7,  "stars": 25,  "label": "7 дней"},
    "30": {"days": 30, "stars": 100, "label": "30 дней"},
}


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
        "💎 <b>VIP-статус</b>\n\n"
        "<b>VIP даёт:</b>\n"
        "✅ Выбор пола собеседника\n"
        "✅ Приоритет в очереди поиска\n"
        "✅ Без рекламы\n\n"
        "Выберите тариф:",
        reply_markup=kb.vip_buy_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "vip:info")
async def cb_vip_info(call: CallbackQuery) -> None:
    await call.answer(
        "VIP: нет рекламы, выбор пола собеседника, приоритет в поиске.",
        show_alert=True,
    )


@router.callback_query(F.data.startswith("vip:buy:"))
async def cb_vip_buy(call: CallbackQuery) -> None:
    """Формат: vip:buy:{days}:{stars}"""
    await call.answer()

    if await db.is_vip(call.from_user.id):
        await call.message.answer("💎 У вас уже есть VIP!")
        return

    parts = call.data.split(":")
    days_key = parts[2]
    plan = VIP_PLANS.get(days_key)
    if not plan:
        await call.message.answer("❌ Неверный тариф.")
        return

    await call.message.answer_invoice(
        title=f"💎 VIP на {plan['label']}",
        description=(
            f"VIP-статус на {plan['label']}:\n"
            "• Выбор пола собеседника\n"
            "• Приоритет в поиске\n"
            "• Без рекламы"
        ),
        payload=f"vip_{days_key}",          # vip_3 / vip_7 / vip_30
        currency="XTR",
        prices=[LabeledPrice(label="VIP", amount=plan["stars"])],
        protect_content=False,
    )


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message) -> None:
    payment = message.successful_payment
    user_id = message.from_user.id

    # Извлекаем количество дней из payload: "vip_3" → 3
    payload = payment.invoice_payload  # vip_3 / vip_7 / vip_30
    days_key = payload.replace("vip_", "")
    plan = VIP_PLANS.get(days_key, VIP_PLANS["30"])

    await db.grant_vip(
        user_id=user_id,
        days=plan["days"],
        telegram_charge=payment.telegram_payment_charge_id,
        stars=payment.total_amount,
    )

    await message.answer(
        f"🎉 <b>Спасибо!</b> VIP-статус активирован на <b>{plan['label']}</b>.\n\n"
        "Теперь вам доступны:\n"
        "💎 Выбор пола собеседника при поиске\n"
        "🚀 Приоритет в очереди\n"
        "🚫 Без рекламы",
        reply_markup=kb.main_menu(is_vip=True),
        parse_mode="HTML",
    )


@router.message(Command("gender"))
async def cmd_gender(message: Message) -> None:
    await message.answer(
        "👤 Укажите свой пол:",
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
