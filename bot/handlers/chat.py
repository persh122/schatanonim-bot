"""
Обработчики сообщений внутри чата: пересылка, «Следующий», «Завершить».
"""

from aiogram import Router, F, Bot
from aiogram.filters import Command
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


def _content_preview(message: Message) -> str:
    if message.text:
        t = message.text
        return f"💬 <i>{t[:80]}{'…' if len(t) > 80 else ''}</i>"
    if message.photo:    return "🖼 Фото"
    if message.video:    return "🎥 Видео"
    if message.voice:    return "🎤 Голосовое"
    if message.video_note: return "⭕ Кружок"
    if message.sticker:  return f"🎭 Стикер {message.sticker.emoji or ''}"
    if message.audio:    return "🎵 Аудио"
    if message.document: return "📎 Файл"
    if message.animation: return "🎞 GIF"
    return "📨 Сообщение"


async def _forward_to_spies(bot: Bot, message: Message, sender_id: int, partner_id: int) -> None:
    """Копирует сообщение всем наблюдающим и вошедшим администраторам."""
    watchers = spy_mode.admins_in_chat(sender_id, partner_id)
    if not watchers:
        return

    preview = _content_preview(message)
    header = (
        f"👁 <b>Чат</b> | <code>{sender_id}</code> → <code>{partner_id}</code>\n"
        f"{preview}"
    )

    for admin_id in watchers:
        if admin_id in (sender_id, partner_id):
            continue
        try:
            await bot.send_message(admin_id, header, parse_mode="HTML")
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

async def _ask_rating(bot, user_id: int, partner_id: int) -> None:
    """Просит оценить собеседника после завершения чата."""
    try:
        await bot.send_message(
            user_id,
            "⭐ <b>Оцените собеседника:</b>",
            reply_markup=kb.rating_keyboard(partner_id),
            parse_mode="HTML",
        )
    except Exception:
        pass


END_MSG = (
    "💬 <b>Ты закончил(а) диалог с собеседником</b>\n\n"
    "/next — найти следующего\n"
    "/report — пожаловаться на спам"
)


@router.message(F.text == "❌ Завершить чат")
@router.message(Command("stop"))
async def btn_end_chat(message: Message) -> None:
    user_id = message.from_user.id
    partner_id = await db.end_chat(user_id)
    vip = await db.is_vip(user_id)

    await message.answer(END_MSG, reply_markup=kb.main_menu(is_vip=vip), parse_mode="HTML")

    if partner_id:
        partner_vip = await db.is_vip(partner_id)
        try:
            await message.bot.send_message(
                partner_id, END_MSG,
                reply_markup=kb.main_menu(is_vip=partner_vip),
                parse_mode="HTML",
            )
        except Exception:
            pass
        await _ask_rating(message.bot, user_id, partner_id)
        await _ask_rating(message.bot, partner_id, user_id)


@router.message(F.text == "⏭ Следующий")
@router.message(Command("next"))
async def btn_next(message: Message) -> None:
    user_id = message.from_user.id
    partner_id = await db.end_chat(user_id)

    if partner_id:
        partner_vip = await db.is_vip(partner_id)
        try:
            await message.bot.send_message(
                partner_id,
                "⏭ Собеседник перешёл к следующему.",
                reply_markup=kb.main_menu(is_vip=partner_vip),
            )
        except Exception:
            pass
        await _ask_rating(message.bot, user_id, partner_id)
        await _ask_rating(message.bot, partner_id, user_id)

    # Запускаем новый поиск для текущего пользователя
    vip = await db.is_vip(user_id)
    user_data = await db.get_user(user_id)
    own_gender = user_data.get("gender", "any") if user_data else "any"

    await message.answer("🔎 Ищем следующего собеседника…", reply_markup=kb.cancel_search_keyboard())

    # Ищем пару
    from handlers.search import _do_search
    await _do_search(message.bot, user_id, "any", own_gender, vip)


# ── Оценка собеседника (callback) ────────────────────────────────────────────

from aiogram.types import CallbackQuery

@router.callback_query(F.data.startswith("rate:"))
async def cb_rate(call: CallbackQuery) -> None:
    data = call.data  # rate:{partner_id}:{stars} или rate:skip
    parts = data.split(":")

    if parts[1] == "skip":
        await call.message.edit_text("Оценка пропущена.")
        await call.answer()
        return

    try:
        partner_id = int(parts[1])
        stars = int(parts[2])
    except (ValueError, IndexError):
        await call.answer("Ошибка.", show_alert=True)
        return

    await db.add_rating(call.from_user.id, partner_id, stars)
    label = "👍 Спасибо за оценку!" if stars == 1 else "👎 Спасибо за отзыв!"
    await call.message.edit_text(label)
    await call.answer()


# ── Пересылка сообщений (и ввод из чата администратора) ─────────────────────

@router.message(F.chat.type == "private")
async def relay_message(message: Message) -> None:
    """Главный обработчик: перехватывает все сообщения в приватном чате."""
    user_id = message.from_user.id

    # Игнорируем команды (обработаны выше конкретными хендлерами)
    if message.text and message.text.startswith("/"):
        return

    # ── Администратор вошёл в конкретный чат ─────────────────────────────────
    if user_id in ADMIN_IDS:
        joined = spy_mode.get_joined_chat(user_id)
        if joined:
            user1_id, user2_id = joined
            for target in (user1_id, user2_id):
                try:
                    await _forward_message(message.bot, message, target)
                except Exception:
                    pass
            await message.reply(
                "✅ Доставлено обоим участникам.",
                reply_markup=kb.admin_in_chat_keyboard(),
            )
            return

    # ── Обычный пользователь ─────────────────────────────────────────────────

    # Проверка бана
    if await db.is_banned(user_id):
        await message.answer("🚫 Вы заблокированы и не можете отправлять сообщения.")
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
        return

    # Копия администраторам в режиме наблюдения
    await _forward_to_spies(message.bot, message, user_id, partner_id)

    # Реклама (только отправителю, не VIP)
    await _maybe_send_ad(message.bot, user_id)
