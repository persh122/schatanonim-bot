"""
Анонимные сообщения — стиль @MessageAnonBot.
Поток:
  1. Пользователь делится ссылкой t.me/BotName?start=anon_{user_id}
  2. Кто-то открывает ссылку → бот спрашивает «Напишите сообщение»
  3. Сообщение доставляется получателю анонимно
  4. Получатель может ответить или заблокировать отправителя
"""

import uuid
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
import keyboards as kb

logger = logging.getLogger(__name__)
router = Router()


# ── FSM-состояния ────────────────────────────────────────────────────────────

class AnonStates(StatesGroup):
    composing = State()   # пишем анонимное сообщение (data: target_id)
    replying  = State()   # отвечаем на анонимное сообщение (data: token)


# ── Получить личную ссылку ───────────────────────────────────────────────────

@router.message(Command("link"))
@router.message(F.text == "🔗 Моя ссылка")
async def cmd_my_link(message: Message) -> None:
    user_id = message.from_user.id
    bot_info = await message.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=anon_{user_id}"

    await message.answer(
        f"🔗 <b>Ваша анонимная ссылка:</b>\n\n"
        f"<code>{link}</code>\n\n"
        "Поделитесь ею в профиле, историях или с друзьями — "
        "и они смогут отправить вам анонимное сообщение!\n\n"
        "📊 Статистика: /stats",
        parse_mode="HTML",
    )


# ── Статистика ───────────────────────────────────────────────────────────────

@router.message(Command("stats"))
@router.message(F.text == "📊 Статистика")
async def cmd_stats(message: Message) -> None:
    stats = await db.get_anon_stats(message.from_user.id)
    await message.answer(
        f"📊 <b>Ваша статистика</b>\n\n"
        f"📨 Получено сообщений: <b>{stats['received']}</b>\n"
        f"↩️ Ответов отправлено: <b>{stats['replied']}</b>\n"
        f"📤 Отправлено вами: <b>{stats['sent']}</b>",
        parse_mode="HTML",
    )


# ── Точка входа по deep-link ─────────────────────────────────────────────────

async def handle_anon_deep_link(message: Message, target_id: int, state: FSMContext) -> None:
    """Вызывается из handlers/start.py когда /start anon_{id}."""
    sender_id = message.from_user.id

    if sender_id == target_id:
        await message.answer(
            "😅 Нельзя отправить анонимное сообщение самому себе.\n\n"
            "Поделитесь своей ссылкой с другими!",
        )
        return

    # Проверяем, не заблокирован ли отправитель
    if await db.is_blocked(target_id, sender_id):
        await message.answer("❌ Вы не можете отправить сообщение этому пользователю.")
        return

    target = await db.get_user(target_id)
    if not target:
        await message.answer("❌ Пользователь не найден.")
        return

    await state.set_state(AnonStates.composing)
    await state.update_data(target_id=target_id)

    await message.answer(
        "✉️ <b>Отправьте анонимное сообщение</b>\n\n"
        "Напишите текст, отправьте фото, видео, голосовое или стикер — "
        "получатель не узнает, кто вы.\n\n"
        "❌ Для отмены нажмите /cancel",
        reply_markup=kb.cancel_anon_keyboard(),
        parse_mode="HTML",
    )


# ── Отмена ──────────────────────────────────────────────────────────────────

@router.message(Command("cancel"))
@router.message(F.text == "❌ Отмена")
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current in (AnonStates.composing, AnonStates.replying):
        await state.clear()
        vip = await db.is_vip(message.from_user.id)
        await message.answer("Отменено.", reply_markup=kb.main_menu(is_vip=vip))
    # Если нет активного состояния — просто молчим


# ── Отправка анонимного сообщения ────────────────────────────────────────────

@router.message(AnonStates.composing)
async def receive_anon_message(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    target_id: int = data["target_id"]
    sender_id = message.from_user.id
    token = str(uuid.uuid4())

    # Определяем тип и содержимое
    content_type, text, file_id, caption = _extract_content(message)
    if content_type is None:
        await message.answer("⚠️ Этот тип сообщения не поддерживается. Попробуйте другой.")
        return

    # Сохраняем в БД
    await db.save_anon_message(
        token=token,
        sender_id=sender_id,
        receiver_id=target_id,
        content_type=content_type,
        text=text,
        file_id=file_id,
        caption=caption,
    )

    # Доставляем получателю
    try:
        await _deliver_anon_message(
            message.bot, target_id, content_type, text, file_id, caption, token
        )
    except Exception as e:
        logger.warning("Failed to deliver anon message: %s", e)
        await message.answer("⚠️ Не удалось доставить сообщение — пользователь недоступен.")
        await state.clear()
        vip = await db.is_vip(sender_id)
        await message.answer("Возвращаемся в главное меню.", reply_markup=kb.main_menu(is_vip=vip))
        return

    await state.clear()
    vip = await db.is_vip(sender_id)
    await message.answer(
        "✅ <b>Сообщение отправлено анонимно!</b>\n\n"
        "Если получатель ответит — вы получите уведомление.",
        reply_markup=kb.main_menu(is_vip=vip),
        parse_mode="HTML",
    )


async def _deliver_anon_message(
    bot: Bot,
    target_id: int,
    content_type: str,
    text: str | None,
    file_id: str | None,
    caption: str | None,
    token: str,
) -> None:
    """Отправляет анонимное сообщение получателю с кнопками ответа и блокировки."""
    reply_markup = kb.anon_message_keyboard(token)
    prefix = "✉️ <b>Вам анонимное сообщение!</b>\n\n"

    if content_type == "text" and text:
        await bot.send_message(
            target_id,
            prefix + text,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
    elif content_type == "photo" and file_id:
        cap = (prefix + caption) if caption else prefix.rstrip()
        await bot.send_photo(
            target_id, file_id, caption=cap,
            reply_markup=reply_markup, parse_mode="HTML",
        )
    elif content_type == "video" and file_id:
        cap = (prefix + caption) if caption else prefix.rstrip()
        await bot.send_video(
            target_id, file_id, caption=cap,
            reply_markup=reply_markup, parse_mode="HTML",
        )
    elif content_type == "voice" and file_id:
        await bot.send_voice(
            target_id, file_id,
            caption=prefix.rstrip(),
            reply_markup=reply_markup, parse_mode="HTML",
        )
    elif content_type == "video_note" and file_id:
        await bot.send_message(target_id, prefix.rstrip(), parse_mode="HTML")
        await bot.send_video_note(target_id, file_id, reply_markup=reply_markup)
    elif content_type == "sticker" and file_id:
        await bot.send_message(target_id, prefix.rstrip(), parse_mode="HTML")
        await bot.send_sticker(target_id, file_id, reply_markup=reply_markup)
    elif content_type == "audio" and file_id:
        cap = (prefix + caption) if caption else prefix.rstrip()
        await bot.send_audio(
            target_id, file_id, caption=cap,
            reply_markup=reply_markup, parse_mode="HTML",
        )
    elif content_type == "document" and file_id:
        cap = (prefix + caption) if caption else prefix.rstrip()
        await bot.send_document(
            target_id, file_id, caption=cap,
            reply_markup=reply_markup, parse_mode="HTML",
        )
    elif content_type == "animation" and file_id:
        cap = (prefix + caption) if caption else prefix.rstrip()
        await bot.send_animation(
            target_id, file_id, caption=cap,
            reply_markup=reply_markup, parse_mode="HTML",
        )
    else:
        await bot.send_message(
            target_id, prefix + "(неподдерживаемый тип)",
            reply_markup=reply_markup, parse_mode="HTML",
        )


# ── Ответ на анонимное сообщение ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("anon_reply:"))
async def cb_anon_reply(call: CallbackQuery, state: FSMContext) -> None:
    token = call.data.split(":", 1)[1]
    msg_data = await db.get_anon_message(token)

    if not msg_data:
        await call.answer("Сообщение не найдено.", show_alert=True)
        return

    if call.from_user.id != msg_data["receiver_id"]:
        await call.answer("Это не ваше сообщение.", show_alert=True)
        return

    await state.set_state(AnonStates.replying)
    await state.update_data(token=token)

    await call.message.answer(
        "↩️ <b>Напишите ответ</b>\n\n"
        "Ваш ответ также будет анонимным — отправитель не увидит ваше имя.\n\n"
        "❌ Для отмены нажмите /cancel",
        reply_markup=kb.cancel_anon_keyboard(),
        parse_mode="HTML",
    )
    await call.answer()


@router.message(AnonStates.replying)
async def send_anon_reply(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    token: str = data["token"]

    msg_data = await db.get_anon_message(token)
    if not msg_data:
        await state.clear()
        await message.answer("⚠️ Исходное сообщение не найдено.")
        return

    sender_id = msg_data["sender_id"]
    content_type, text, file_id, caption = _extract_content(message)
    if content_type is None:
        await message.answer("⚠️ Этот тип ответа не поддерживается.")
        return

    # Доставляем ответ оригинальному отправителю
    try:
        prefix = "↩️ <b>Вам ответили на анонимное сообщение!</b>\n\n"
        await _deliver_reply(message.bot, sender_id, content_type, text, file_id, caption, prefix)
        await db.mark_replied(token)
    except Exception as e:
        logger.warning("Failed to deliver reply: %s", e)
        await message.answer("⚠️ Не удалось доставить ответ.")
        await state.clear()
        return

    await state.clear()
    vip = await db.is_vip(message.from_user.id)
    await message.answer(
        "✅ Ответ отправлен анонимно!",
        reply_markup=kb.main_menu(is_vip=vip),
        parse_mode="HTML",
    )


async def _deliver_reply(
    bot: Bot, target_id: int,
    content_type: str, text: str | None,
    file_id: str | None, caption: str | None,
    prefix: str,
) -> None:
    if content_type == "text" and text:
        await bot.send_message(target_id, prefix + text, parse_mode="HTML")
    elif content_type == "photo" and file_id:
        await bot.send_photo(target_id, file_id,
                             caption=(prefix + caption) if caption else prefix.rstrip(),
                             parse_mode="HTML")
    elif content_type == "video" and file_id:
        await bot.send_video(target_id, file_id,
                             caption=(prefix + caption) if caption else prefix.rstrip(),
                             parse_mode="HTML")
    elif content_type == "voice" and file_id:
        await bot.send_voice(target_id, file_id,
                             caption=prefix.rstrip(), parse_mode="HTML")
    elif content_type == "sticker" and file_id:
        await bot.send_message(target_id, prefix.rstrip(), parse_mode="HTML")
        await bot.send_sticker(target_id, file_id)
    elif content_type == "audio" and file_id:
        await bot.send_audio(target_id, file_id,
                             caption=(prefix + caption) if caption else prefix.rstrip(),
                             parse_mode="HTML")
    elif content_type == "document" and file_id:
        await bot.send_document(target_id, file_id,
                                caption=(prefix + caption) if caption else prefix.rstrip(),
                                parse_mode="HTML")
    elif content_type == "animation" and file_id:
        await bot.send_animation(target_id, file_id,
                                 caption=(prefix + caption) if caption else prefix.rstrip(),
                                 parse_mode="HTML")
    else:
        await bot.send_message(target_id, prefix + "(вложение)", parse_mode="HTML")


# ── Блокировка отправителя ───────────────────────────────────────────────────

@router.callback_query(F.data.startswith("anon_block:"))
async def cb_anon_block(call: CallbackQuery) -> None:
    token = call.data.split(":", 1)[1]
    msg_data = await db.get_anon_message(token)

    if not msg_data:
        await call.answer("Сообщение не найдено.", show_alert=True)
        return

    if call.from_user.id != msg_data["receiver_id"]:
        await call.answer("Это не ваше сообщение.", show_alert=True)
        return

    await db.block_sender(call.from_user.id, token)
    await call.answer("🚫 Отправитель заблокирован.", show_alert=True)

    # Убираем кнопки с сообщения
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


# ── Утилиты ──────────────────────────────────────────────────────────────────

def _extract_content(message: Message) -> tuple[str | None, str | None, str | None, str | None]:
    """Возвращает (content_type, text, file_id, caption)."""
    if message.text:
        return "text", message.text, None, None
    if message.photo:
        return "photo", None, message.photo[-1].file_id, message.caption
    if message.video:
        return "video", None, message.video.file_id, message.caption
    if message.voice:
        return "voice", None, message.voice.file_id, None
    if message.video_note:
        return "video_note", None, message.video_note.file_id, None
    if message.sticker:
        return "sticker", None, message.sticker.file_id, None
    if message.audio:
        return "audio", None, message.audio.file_id, message.caption
    if message.document:
        return "document", None, message.document.file_id, message.caption
    if message.animation:
        return "animation", None, message.animation.file_id, message.caption
    return None, None, None, None
