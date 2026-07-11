"""
Обработчики сообщений внутри чата: пересылка, «Следующий», «Завершить».
"""

from aiogram import Router, F, Bot
from aiogram.types import Message

import database as db
import keyboards as kb
import spy as spy_mode
from config import AD_INTERVAL, AD_TEXT, ADMIN_IDS

router = Router()


async def _forward_message(bot: Bot, message: Message, partner_id: int) -> None:
    """Анонимно пересылает сообщение партнёру (поддерживает все типы контента)."""
    msg = message

    # Функции-пересыльщики для каждого типа
    if msg.text:
        await bot.send_message(partner_id, msg.text, entities=msg.entities)

    elif msg.photo:
        await bot.send_photo(
            partner_id, msg.photo[-1].file_id, caption=msg.caption,
            caption_entities=msg.caption_entities,
        )

    elif msg.video:
        await bot.send_video(
            partner_id, msg.video.file_id, caption=msg.caption,
            caption_entities=msg.caption_entities,
        )

    elif msg.voice:
        await bot.send_voice(partner_id, msg.voice.file_id, caption=msg.caption)

    elif msg.video_note:
        await bot.send_video_note(partner_id, msg.video_note.file_id)

    elif msg.audio:
        await bot.send_audio(
            partner_id, msg.audio.file_id, caption=msg.caption,
            caption_entities=msg.caption_entities,
        )

    elif msg.document:
        await bot.send_document(
            partner_id, msg.document.file_id, caption=msg.caption,
            caption_entities=msg.caption_entities,
        )

    elif msg.sticker:
        await bot.send_sticker(partner_id, msg.sticker.file_id)

    elif msg.animation:
        await bot.send_animation(
            partner_id, msg.animation.file_id, caption=msg.caption,
            caption_entities=msg.caption_entities,
        )

    elif msg.location:
        await bot.send_location(partner_id, msg.location.latitude, msg.location.longitude)

    elif msg.contact:
        await bot.send_contact(
            partner_id, msg.contact.phone_number, msg.contact.first_name,
            last_name=msg.contact.last_name,
        )

    else:
        await bot.send_message(partner_id, "⚠️ Этот тип сообщения не поддерживается.")


async def _forward_to_spies(bot: Bot, message: Message, sender_id: int, partner_id: int) -> None:
    """Копирует сообщение всем администраторам с включённым режимом наблюдения."""
    watchers = spy_mode.all_active()
    if not watchers:
        return

    # Определяем тип контента для заголовка
    if message.text:
        preview = f"💬 <i>{message.text[:80]}</i>" if len(message.text) <= 80 else f"💬 <i>{message.text[:80]}…</i>"
    elif message.photo:
        preview = "🖼 Фото"
    elif message.video:
        preview = "🎥 Видео"
    elif message.voice:
        preview = "🎤 Голосовое"
    elif message.video_note:
        preview = "⭕ Кружок"
    elif message.sticker:
        preview = f"🎭 Стикер {message.sticker.emoji or ''}"
    elif message.audio:
        preview = "🎵 Аудио"
    elif message.document:
        preview = "📎 Файл"
    elif message.animation:
        preview = "🎞 GIF"
    else:
        preview = "📨 Сообщение"

    header = (
        f"👁 <b>Чат</b> | <code>{sender_id}</code> → <code>{partner_id}</code>\n"
        f"{preview}"
    )

    for admin_id in watchers:
        if admin_id in (sender_id, partner_id):
            continue
        try:
            await bot.send_message(admin_id, header, parse_mode="HTML")
            # Пересылаем само сообщение без указания отправителя
            await bot.forward_message(admin_id, message.chat.id, message.message_id)
        except Exception:
            pass


async def _maybe_send_ad(bot: Bot, user_id: int) -> None:
    """Отправляет рекламу не-VIP пользователям каждые AD_INTERVAL сообщений."""
    vip = await db.is_vip(user_id)
    if vip:
        return
    count = await db.increment_messages(user_id)
    if count % AD_INTERVAL == 0:
        await bot.send_message(user_id, AD_TEXT, parse_mode="HTML")


# ── Кнопки управления чатом ──────────────────────────────────────────────────

@router.message(F.text == "❌ Завершить чат")
async def btn_end_chat(message: Message) -> None:
    user_id = message.from_user.id
    partner_id = await db.end_chat(user_id)
    vip = await db.is_vip(user_id)

    await message.answer(
        "❌ Чат завершён. Надеемся, вам понравилось общение!\n\n"
        "Нажми <b>🔎 Найти собеседника</b>, чтобы начать новый чат.",
        reply_markup=kb.main_menu(is_vip=vip),
        parse_mode="HTML",
    )

    if partner_id:
        partner_vip = await db.is_vip(partner_id)
        try:
            await message.bot.send_message(
                partner_id,
                "❌ Собеседник завершил чат.\n\n"
                "Нажми <b>🔎 Найти собеседника</b>, чтобы начать новый.",
                reply_markup=kb.main_menu(is_vip=partner_vip),
                parse_mode="HTML",
            )
        except Exception:
            pass


@router.message(F.text == "⏭ Следующий")
async def btn_next(message: Message) -> None:
    user_id = message.from_user.id
    partner_id = await db.end_chat(user_id)

    if partner_id:
        partner_vip = await db.is_vip(partner_id)
        try:
            await message.bot.send_message(
                partner_id,
                "⏭ Собеседник перешёл к следующему.\n\n"
                "Нажми <b>🔎 Найти собеседника</b>, чтобы найти нового.",
                reply_markup=kb.main_menu(is_vip=partner_vip),
                parse_mode="HTML",
            )
        except Exception:
            pass

    # Запускаем новый поиск для текущего пользователя
    vip = await db.is_vip(user_id)
    user_data = await db.get_user(user_id)
    own_gender = user_data.get("gender", "any") if user_data else "any"

    await message.answer("🔎 Ищем следующего собеседника…", reply_markup=kb.cancel_search_keyboard())

    # Ищем пару
    from handlers.search import _do_search
    await _do_search(message.bot, user_id, "any", own_gender, vip)


# ── Пересылка сообщений ──────────────────────────────────────────────────────

@router.message(F.chat.type == "private")
async def relay_message(message: Message) -> None:
    """Главный обработчик: перехватывает все сообщения в приватном чате."""
    user_id = message.from_user.id

    # Проверка бана
    if await db.is_banned(user_id):
        await message.answer("🚫 Вы заблокированы и не можете отправлять сообщения.")
        return

    # Игнорируем системные кнопки (уже обработаны выше)
    if message.text and message.text.startswith("/"):
        return

    partner_id = await db.get_partner(user_id)

    if not partner_id:
        # Пользователь не в чате и не нажал кнопку — подсказываем
        if not await db.is_in_queue(user_id):
            vip = await db.is_vip(user_id)
            await message.answer(
                "Нажми <b>🔎 Найти собеседника</b>, чтобы начать общение.",
                reply_markup=kb.main_menu(is_vip=vip),
                parse_mode="HTML",
            )
        return

    # Пересылаем сообщение партнёру
    try:
        await _forward_message(message.bot, message, partner_id)
    except Exception as e:
        err_str = str(e).lower()
        # Завершаем чат только при подтверждённых постоянных ошибках:
        # пользователь заблокировал бота или деактивировал аккаунт.
        permanent = any(kw in err_str for kw in (
            "bot was blocked", "user is deactivated",
            "chat not found", "forbidden", "kicked",
        ))
        if permanent:
            await db.end_chat(user_id)
            vip = await db.is_vip(user_id)
            await message.answer(
                "⚠️ Собеседник недоступен. Чат завершён.",
                reply_markup=kb.main_menu(is_vip=vip),
            )
        # При временных сетевых ошибках — тихо пропускаем,
        # не завершая чат (пользователи могут продолжить позже)
        return

    # Копия администраторам в режиме наблюдения
    await _forward_to_spies(message.bot, message, user_id, partner_id)

    # Реклама (только отправителю, не VIP)
    await _maybe_send_ad(message.bot, user_id)
