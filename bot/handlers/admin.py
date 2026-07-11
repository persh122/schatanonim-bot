"""
Админ-панель: статистика, бан/разбан, выдача VIP, рассылка.
Доступна только пользователям из ADMIN_IDS.
"""

from aiogram import Router, F
from aiogram.filters import Command
from database import get_user_count
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
import keyboards as kb
import spy as spy_mode
from config import ADMIN_IDS, VIP_DURATION_DAYS

router = Router()


# ── FSM для ввода данных ─────────────────────────────────────────────────────

class AdminStates(StatesGroup):
    waiting_ban_id      = State()
    waiting_unban_id    = State()
    waiting_vip_id      = State()
    waiting_broadcast    = State()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ── Декоратор-проверка прав ──────────────────────────────────────────────────

def admin_only(handler):
    async def wrapper(event, *args, **kwargs):
        uid = event.from_user.id if hasattr(event, "from_user") else None
        if not uid or not is_admin(uid):
            if hasattr(event, "answer"):
                await event.answer("❌ Нет доступа.")
            return
        return await handler(event, *args, **kwargs)
    return wrapper


# ── Главная панель ───────────────────────────────────────────────────────────

@router.message(Command("users"))
async def cmd_users(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    stats = await db.get_stats()
    count = await get_user_count()
    await message.answer(
        f"👥 <b>Пользователей:</b> {count}\n"
        f"🟢 Активных чатов: {stats['active_chats']}\n"
        f"🔎 В очереди: {stats['in_queue']}\n"
        f"💎 VIP: {stats['vip_users']}\n"
        f"🚫 Забанено: {stats['banned_users']}",
        parse_mode="HTML",
    )


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к админ-панели.")
        return

    spy_on = spy_mode.is_active(message.from_user.id)
    await message.answer(
        "🛠 <b>Админ-панель</b>\n\nВыберите действие:",
        reply_markup=kb.admin_keyboard(spy_on=spy_on),
        parse_mode="HTML",
    )


# ── Активные чаты ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:active_chats")
async def cb_active_chats(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("❌ Нет доступа.", show_alert=True)
        return

    chats = await db.get_active_chats_list()
    count = len(chats)
    await call.message.edit_text(
        f"💬 <b>Активные чаты</b> — {count} пар\n\nВыберите чат для входа:",
        reply_markup=kb.active_chats_keyboard(chats),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.startswith("admin:joinchat:"))
async def cb_join_chat(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("❌ Нет доступа.", show_alert=True)
        return

    parts = call.data.split(":")
    try:
        user1_id = int(parts[2])
        user2_id = int(parts[3])
    except (IndexError, ValueError):
        await call.answer("Ошибка.", show_alert=True)
        return

    # Проверяем что чат ещё активен
    partner = await db.get_partner(user1_id)
    if partner != user2_id:
        await call.answer("❌ Этот чат уже завершён.", show_alert=True)
        chats = await db.get_active_chats_list()
        await call.message.edit_reply_markup(reply_markup=kb.active_chats_keyboard(chats))
        return

    spy_mode.join_chat(call.from_user.id, user1_id, user2_id)

    u1 = await db.get_user(user1_id)
    u2 = await db.get_user(user2_id)
    g = {"male": "👨", "female": "👩"}
    n1 = f"{g.get(u1.get('gender',''),'👤')} {u1.get('age','?')} (ID {user1_id})" if u1 else str(user1_id)
    n2 = f"{g.get(u2.get('gender',''),'👤')} {u2.get('age','?')} (ID {user2_id})" if u2 else str(user2_id)

    await call.message.edit_text(
        f"👁 <b>Вы вошли в чат</b>\n\n"
        f"Участник A: {n1}\n"
        f"Участник B: {n2}\n\n"
        "Все сообщения будут приходить вам.\n"
        "Ваши сообщения уйдут <b>обоим</b> участникам анонимно.\n\n"
        "⚠️ Участники <b>не знают</b> о вашем присутствии.",
        reply_markup=kb.admin_in_chat_keyboard(),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data == "admin:leavechat")
async def cb_leave_chat(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("❌ Нет доступа.", show_alert=True)
        return

    spy_mode.leave_chat(call.from_user.id)
    spy_on = spy_mode.is_active(call.from_user.id)
    await call.message.edit_text(
        "🚪 Вы вышли из чата.\n\n🛠 <b>Админ-панель</b>\n\nВыберите действие:",
        reply_markup=kb.admin_keyboard(spy_on=spy_on),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data == "admin:back")
async def cb_admin_back(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("❌ Нет доступа.", show_alert=True)
        return
    spy_on = spy_mode.is_active(call.from_user.id)
    await call.message.edit_text(
        "🛠 <b>Админ-панель</b>\n\nВыберите действие:",
        reply_markup=kb.admin_keyboard(spy_on=spy_on),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data == "admin:noop")
async def cb_noop(call: CallbackQuery) -> None:
    await call.answer()


# ── Режим наблюдения ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:spy")
async def cb_spy_toggle(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("❌ Нет доступа.", show_alert=True)
        return

    now_on = spy_mode.toggle(call.from_user.id)
    status = "🟢 включён" if now_on else "🔴 выключен"
    await call.answer(f"👁 Режим наблюдения {status}", show_alert=True)
    await call.message.edit_reply_markup(
        reply_markup=kb.admin_keyboard(spy_on=now_on)
    )


# ── Статистика ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:stats")
async def cb_stats(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("❌ Нет доступа.", show_alert=True)
        return

    stats = await db.get_stats()
    await call.message.edit_text(
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Пользователей: <b>{stats['total_users']}</b>\n"
        f"💎 VIP: <b>{stats['vip_users']}</b>\n"
        f"🚫 Забанено: <b>{stats['banned_users']}</b>\n"
        f"💬 Активных чатов: <b>{stats['active_chats']}</b>\n"
        f"🔎 В очереди: <b>{stats['in_queue']}</b>\n"
        f"📨 Сообщений всего: <b>{stats['total_messages']}</b>\n"
        f"⭐ Звёзд получено: <b>{stats['total_stars']}</b>",
        reply_markup=kb.admin_keyboard(),
        parse_mode="HTML",
    )
    await call.answer()


# ── Жалобы ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:reports")
async def cb_reports(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("❌ Нет доступа.", show_alert=True)
        return

    reports = await db.get_reports(limit=20)
    if not reports:
        await call.message.edit_text(
            "🚨 <b>Жалобы</b>\n\nЖалоб пока нет.",
            reply_markup=kb.admin_keyboard(),
            parse_mode="HTML",
        )
        await call.answer()
        return

    lines = []
    for r in reports:
        name = f"@{r['username']}" if r.get('username') else f"id:{r['reported_id']}"
        lines.append(
            f"• {name} (<code>{r['reported_id']}</code>) — "
            f"<b>{r['total']} жал.</b> | {r['reason'] or '—'}"
        )

    text = "🚨 <b>Последние жалобы (топ 20)</b>\n\n" + "\n".join(lines)
    # Telegram ограничение 4096 символов
    if len(text) > 4000:
        text = text[:3997] + "…"

    await call.message.edit_text(text, reply_markup=kb.admin_keyboard(), parse_mode="HTML")
    await call.answer()


# ── Бан ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:ban")
async def cb_ban_prompt(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("❌ Нет доступа.", show_alert=True)
        return

    await call.message.answer("Введите <b>ID пользователя</b> для бана:", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_ban_id)
    await call.answer()


@router.message(AdminStates.waiting_ban_id)
async def process_ban(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    try:
        uid = int(message.text.strip())
        await db.ban_user(uid)
        # Завершаем чат, если есть
        await db.end_chat(uid)
        await db.remove_from_queue(uid)
        await message.answer(f"✅ Пользователь <code>{uid}</code> забанен.", parse_mode="HTML")
        try:
            await message.bot.send_message(uid, "🚫 Вы были заблокированы администратором.")
        except Exception:
            pass
    except ValueError:
        await message.answer("❌ Некорректный ID.")
    await state.clear()


# ── Разбан ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:unban")
async def cb_unban_prompt(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("❌ Нет доступа.", show_alert=True)
        return

    await call.message.answer("Введите <b>ID пользователя</b> для разбана:", parse_mode="HTML")
    await state.set_state(AdminStates.waiting_unban_id)
    await call.answer()


@router.message(AdminStates.waiting_unban_id)
async def process_unban(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    try:
        uid = int(message.text.strip())
        await db.unban_user(uid)
        await message.answer(f"✅ Пользователь <code>{uid}</code> разбанен.", parse_mode="HTML")
        try:
            await message.bot.send_message(uid, "✅ Ваш аккаунт разблокирован. Добро пожаловать!")
        except Exception:
            pass
    except ValueError:
        await message.answer("❌ Некорректный ID.")
    await state.clear()


# ── Выдать VIP ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:givevip")
async def cb_givevip_prompt(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("❌ Нет доступа.", show_alert=True)
        return

    await call.message.answer(
        "Введите <b>ID пользователя</b> для выдачи VIP:", parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_vip_id)
    await call.answer()


@router.message(AdminStates.waiting_vip_id)
async def process_give_vip(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    try:
        uid = int(message.text.strip())
        await db.grant_vip(uid, VIP_DURATION_DAYS, None, 0)
        await message.answer(
            f"✅ VIP выдан пользователю <code>{uid}</code> на {VIP_DURATION_DAYS} дней.",
            parse_mode="HTML",
        )
        try:
            await message.bot.send_message(
                uid,
                f"🎁 Администратор выдал вам <b>VIP на {VIP_DURATION_DAYS} дней</b>!\n"
                "Наслаждайтесь привилегиями.",
                parse_mode="HTML",
            )
        except Exception:
            pass
    except ValueError:
        await message.answer("❌ Некорректный ID.")
    await state.clear()


# ── Рассылка ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:broadcast")
async def cb_broadcast_prompt(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("❌ Нет доступа.", show_alert=True)
        return

    await call.message.answer(
        "📣 Введите текст для рассылки всем пользователям:\n\n"
        "(поддерживается HTML-разметка)"
    )
    await state.set_state(AdminStates.waiting_broadcast)
    await call.answer()


@router.message(AdminStates.waiting_broadcast)
async def process_broadcast(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    text = message.text or message.caption or ""
    users = await db.get_all_users(limit=10000)

    sent, failed = 0, 0
    status_msg = await message.answer(f"📣 Рассылка начата... (0/{len(users)})")

    for i, user in enumerate(users):
        try:
            await message.bot.send_message(user["user_id"], text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1

        # Обновляем статус каждые 50 пользователей
        if (i + 1) % 50 == 0:
            try:
                await status_msg.edit_text(
                    f"📣 Рассылка: {i + 1}/{len(users)}..."
                )
            except Exception:
                pass

    await status_msg.edit_text(
        f"✅ Рассылка завершена!\n\n"
        f"Доставлено: {sent}\nОшибок: {failed}"
    )
    await state.clear()


# ── Список пользователей ─────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:users")
async def cb_users_list(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("❌ Нет доступа.", show_alert=True)
        return

    users = await db.get_all_users(limit=20)
    if not users:
        await call.message.answer("Пользователей пока нет.")
        await call.answer()
        return

    lines = []
    for u in users:
        vip_mark = "💎" if u["is_vip"] else "  "
        ban_mark = "🚫" if u["is_banned"] else "  "
        name = u["first_name"] or "—"
        lines.append(f"{vip_mark}{ban_mark} <code>{u['user_id']}</code> {name} | чатов: {u['total_chats']}")

    await call.message.answer(
        "👥 <b>Последние 20 пользователей:</b>\n\n" + "\n".join(lines),
        parse_mode="HTML",
    )
    await call.answer()
