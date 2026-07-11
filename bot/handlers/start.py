"""
/start, регистрация (выбор пола → ввод возраста), /help, профиль.
"""

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
import keyboards as kb

router = Router()


# ── FSM регистрации ──────────────────────────────────────────────────────────

class RegStates(StatesGroup):
    choosing_gender = State()
    entering_age    = State()


# ── /start ────────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    user = message.from_user
    await db.register_user(user.id, user.username, user.first_name)

    # Если уже зарегистрирован — просто показываем меню
    if await db.is_registered(user.id):
        vip = await db.is_vip(user.id)
        await message.answer(
            "👋 С возвращением!\n\nВыбери действие в меню ниже.",
            reply_markup=kb.main_menu(is_vip=vip),
        )
        return

    # Начинаем регистрацию
    await state.set_state(RegStates.choosing_gender)
    await message.answer(
        f"👋 Привет, <b>{user.first_name}</b>!\n\n"
        "Добро пожаловать в <b>Анонимный чат</b>.\n\n"
        "Для начала пройди быструю регистрацию.\n\n"
        "Шаг 1 из 2 — <b>Выбери свой пол:</b>",
        reply_markup=kb.reg_gender_keyboard(),
        parse_mode="HTML",
    )


# ── Шаг 1: выбор пола ────────────────────────────────────────────────────────

@router.callback_query(RegStates.choosing_gender, F.data.startswith("reg_gender:"))
async def cb_reg_gender(call: CallbackQuery, state: FSMContext) -> None:
    gender = call.data.split(":")[1]  # male | female
    await state.update_data(gender=gender)
    await state.set_state(RegStates.entering_age)

    label = "👨 Мужской" if gender == "male" else "👩 Женский"
    await call.message.edit_text(
        f"✅ Пол: <b>{label}</b>\n\n"
        "Шаг 2 из 2 — <b>Введи свой возраст</b> (от 18 до 99):",
        parse_mode="HTML",
    )
    await call.answer()


# ── Шаг 2: ввод возраста ─────────────────────────────────────────────────────

@router.message(RegStates.entering_age)
async def reg_enter_age(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()

    # Валидация
    if not text.isdigit():
        await message.answer("⚠️ Введи число от 18 до 99.")
        return

    age = int(text)
    if age < 18 or age > 99:
        await message.answer("⚠️ Возраст должен быть от <b>18</b> до <b>99</b> лет.", parse_mode="HTML")
        return

    data = await state.get_data()
    gender = data.get("gender", "male")
    await db.complete_registration(message.from_user.id, gender, age)
    await state.clear()

    vip = await db.is_vip(message.from_user.id)
    gender_label = "👨 Мужской" if gender == "male" else "👩 Женский"

    await message.answer(
        f"🎉 <b>Регистрация завершена!</b>\n\n"
        f"Пол: <b>{gender_label}</b>\n"
        f"Возраст: <b>{age}</b>\n\n"
        "Теперь ты можешь начать общение!\n"
        "🔎 Найди собеседника или попробуй 🔥 Флирт чат.",
        reply_markup=kb.main_menu(is_vip=vip),
        parse_mode="HTML",
    )


# ── /help ─────────────────────────────────────────────────────────────────────

@router.message(Command("help"))
@router.message(F.text == "ℹ️ Помощь")
async def cmd_help(message: Message) -> None:
    await message.answer(
        "📖 <b>Помощь</b>\n\n"
        "<b>Кнопки:</b>\n"
        "🔎 Найти собеседника — случайный анонимный чат\n"
        "🔥 Флирт чат — поиск в режиме флирта\n"
        "⏭ Следующий — сменить собеседника\n"
        "❌ Завершить чат — выйти из чата\n\n"
        "<b>Что можно отправлять:</b>\n"
        "Текст, фото, видео, голосовые,\n"
        "кружки, стикеры, файлы и аудио\n\n"
        "<b>Команды:</b>\n"
        "/profile — мой профиль\n"
        "/gender — сменить пол\n"
        "/age — сменить возраст\n"
        "/vip — VIP-подписка\n\n"
        "🔒 Все чаты полностью анонимны.",
        parse_mode="HTML",
    )


@router.message(Command("menu"))
@router.message(F.text == "🏠 Главное меню")
async def cmd_main_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    vip = await db.is_vip(message.from_user.id)
    await message.answer(
        "🏠 <b>Главное меню</b>",
        reply_markup=kb.main_menu(is_vip=vip),
        parse_mode="HTML",
    )



# ── Профиль ───────────────────────────────────────────────────────────────────

@router.message(Command("profile"))
@router.message(F.text == "👤 Мой профиль")
async def cmd_profile(message: Message) -> None:
    user_data = await db.get_user(message.from_user.id)
    if not user_data:
        await message.answer("Сначала напиши /start")
        return

    vip_status = "💎 VIP" if user_data["is_vip"] else "👤 Обычный"
    vip_until = ""
    if user_data["is_vip"] and user_data["vip_until"]:
        vip_until = f"\nVIP до: <code>{user_data['vip_until'][:10]}</code>"

    gender_map = {"male": "👨 Мужской", "female": "👩 Женский", "any": "—"}
    gender = gender_map.get(user_data.get("gender", "any"), "—")
    age = user_data.get("age") or "—"
    avg = await db.get_avg_rating(message.from_user.id)
    rating_str = f"⭐ {avg}" if avg is not None else "—"

    await message.answer(
        f"<b>Мой профиль</b>\n\n"
        f"ID: <code>{user_data['user_id']}</code>\n"
        f"Статус: {vip_status}{vip_until}\n"
        f"Пол: {gender}\n"
        f"Возраст: {age}\n"
        f"Рейтинг: {rating_str}\n"
        f"Чатов: {user_data['total_chats']}\n"
        f"Сообщений: {user_data['messages_sent']}\n\n"
        "Изменить: /gender | /age",
        parse_mode="HTML",
    )


# ── Смена возраста (/age) ─────────────────────────────────────────────────────

class AgeChangeState(StatesGroup):
    entering = State()


@router.message(Command("age"))
async def cmd_change_age(message: Message, state: FSMContext) -> None:
    await state.set_state(AgeChangeState.entering)
    await message.answer(
        "Введи новый возраст (от 18 до 99):",
        reply_markup=kb.remove_keyboard(),
    )


@router.message(AgeChangeState.entering)
async def process_age_change(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("⚠️ Введи число от 18 до 99.")
        return
    age = int(text)
    if age < 18 or age > 99:
        await message.answer("⚠️ Возраст от <b>18</b> до <b>99</b>.", parse_mode="HTML")
        return

    await db.set_age(message.from_user.id, age)
    await state.clear()
    vip = await db.is_vip(message.from_user.id)
    await message.answer(
        f"✅ Вы успешно сменили возраст на: <b>{age}</b>",
        reply_markup=kb.main_menu(is_vip=vip),
        parse_mode="HTML",
    )
