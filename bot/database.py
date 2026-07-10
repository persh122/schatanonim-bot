"""
Модуль работы с базой данных SQLite через aiosqlite.
Все операции асинхронные.
"""

import aiosqlite
import os
from datetime import datetime, timedelta
from config import DB_PATH


# ── Инициализация ────────────────────────────────────────────────────────────

async def init_db() -> None:
    """Создаёт все таблицы, если они не существуют."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            -- Пользователи
            CREATE TABLE IF NOT EXISTS users (
                user_id        INTEGER PRIMARY KEY,
                username       TEXT,
                first_name     TEXT,
                gender         TEXT DEFAULT 'any',   -- 'male' | 'female' | 'any'
                age            INTEGER DEFAULT 0,    -- возраст 18-99 (0 = не указан)
                is_registered  INTEGER DEFAULT 0,    -- 1 = прошёл регистрацию
                is_vip         INTEGER DEFAULT 0,
                vip_until      TEXT,
                is_banned      INTEGER DEFAULT 0,
                registered_at  TEXT DEFAULT (datetime('now')),
                messages_sent  INTEGER DEFAULT 0,
                total_chats    INTEGER DEFAULT 0
            );

            -- Активные чаты (пары пользователей)
            CREATE TABLE IF NOT EXISTS active_chats (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user1_id    INTEGER NOT NULL,
                user2_id    INTEGER NOT NULL,
                started_at  TEXT DEFAULT (datetime('now')),
                UNIQUE(user1_id),
                UNIQUE(user2_id)
            );

            -- Очередь ожидания
            CREATE TABLE IF NOT EXISTS waiting_queue (
                user_id        INTEGER PRIMARY KEY,
                gender_pref    TEXT DEFAULT 'any',   -- предпочитаемый пол собеседника
                own_gender     TEXT DEFAULT 'any',   -- свой пол (для VIP-фильтра)
                is_vip         INTEGER DEFAULT 0,
                chat_mode      TEXT DEFAULT 'normal', -- 'normal' | 'flirt'
                joined_at      TEXT DEFAULT (datetime('now'))
            );

            -- Анонимные сообщения (для личной ссылки)
            CREATE TABLE IF NOT EXISTS anon_messages (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                token        TEXT UNIQUE NOT NULL,  -- UUID для привязки ответа
                sender_id    INTEGER NOT NULL,       -- кто отправил (анонимно)
                receiver_id  INTEGER NOT NULL,       -- кому отправлено
                content_type TEXT NOT NULL,          -- text|photo|video|voice|sticker|document|audio|animation
                file_id      TEXT,                   -- для медиа
                text         TEXT,                   -- текст сообщения
                caption      TEXT,                   -- подпись к медиа
                is_replied   INTEGER DEFAULT 0,
                is_blocked   INTEGER DEFAULT 0,
                sent_at      TEXT DEFAULT (datetime('now'))
            );

            -- Заблокированные отправители (по receiver_id)
            CREATE TABLE IF NOT EXISTS anon_blocks (
                receiver_id  INTEGER NOT NULL,
                sender_id    INTEGER NOT NULL,
                PRIMARY KEY (receiver_id, sender_id)
            );

            -- Журнал платежей (Telegram Stars)
            CREATE TABLE IF NOT EXISTS payments (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                telegram_charge TEXT,
                stars           INTEGER,
                paid_at         TEXT DEFAULT (datetime('now'))
            );
        """)
        await db.commit()


# ── Пользователи ─────────────────────────────────────────────────────────────

async def register_user(user_id: int, username: str | None, first_name: str) -> bool:
    """Регистрирует нового пользователя. Возвращает True, если это первая регистрация."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT user_id FROM users WHERE user_id = ?", (user_id,)
        )
        exists = await cursor.fetchone()
        if not exists:
            await db.execute(
                "INSERT INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                (user_id, username, first_name),
            )
            await db.commit()
            return True
        else:
            # Обновляем username/first_name при каждом /start
            await db.execute(
                "UPDATE users SET username=?, first_name=? WHERE user_id=?",
                (username, first_name, user_id),
            )
            await db.commit()
            return False


async def get_user(user_id: int) -> dict | None:
    """Возвращает данные пользователя или None."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def is_banned(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT is_banned FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return bool(row and row[0])


async def complete_registration(user_id: int, gender: str, age: int) -> None:
    """Завершает регистрацию — сохраняет пол, возраст и ставит флаг."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET gender=?, age=?, is_registered=1 WHERE user_id=?",
            (gender, age, user_id),
        )
        await db.commit()


async def is_registered(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT is_registered FROM users WHERE user_id=?", (user_id,)
        )
        row = await cur.fetchone()
        return bool(row and row[0])


async def set_gender(user_id: int, gender: str) -> None:
    """Устанавливает пол пользователя ('male'|'female'|'any')."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET gender=? WHERE user_id=?", (gender, user_id))
        await db.commit()


async def set_age(user_id: int, age: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET age=? WHERE user_id=?", (age, user_id))
        await db.commit()


async def increment_messages(user_id: int) -> int:
    """Увеличивает счётчик сообщений. Возвращает новое значение."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET messages_sent = messages_sent + 1 WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()
        cur = await db.execute(
            "SELECT messages_sent FROM users WHERE user_id=?", (user_id,)
        )
        row = await cur.fetchone()
        return row[0] if row else 0


async def is_vip(user_id: int) -> bool:
    """Проверяет, является ли пользователь VIP (и не истёк ли срок)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT is_vip, vip_until FROM users WHERE user_id=?", (user_id,)
        )
        row = await cur.fetchone()
        if not row or not row[0]:
            return False
        if row[1]:
            until = datetime.fromisoformat(row[1])
            if datetime.utcnow() > until:
                # Срок истёк — сбрасываем
                await db.execute(
                    "UPDATE users SET is_vip=0, vip_until=NULL WHERE user_id=?",
                    (user_id,),
                )
                await db.commit()
                return False
        return True


async def grant_vip(user_id: int, days: int, telegram_charge: str | None, stars: int) -> None:
    """Выдаёт VIP пользователю."""
    async with aiosqlite.connect(DB_PATH) as db:
        until = (datetime.utcnow() + timedelta(days=days)).isoformat()
        await db.execute(
            "UPDATE users SET is_vip=1, vip_until=? WHERE user_id=?",
            (until, user_id),
        )
        await db.execute(
            "INSERT INTO payments (user_id, telegram_charge, stars) VALUES (?,?,?)",
            (user_id, telegram_charge, stars),
        )
        await db.commit()


async def ban_user(user_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (user_id,))
        await db.commit()


async def unban_user(user_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (user_id,))
        await db.commit()


# ── Очередь ожидания ─────────────────────────────────────────────────────────

async def add_to_queue(
    user_id: int, gender_pref: str, own_gender: str, vip: bool, chat_mode: str = "normal"
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR REPLACE INTO waiting_queue
               (user_id, gender_pref, own_gender, is_vip, chat_mode, joined_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'))""",
            (user_id, gender_pref, own_gender, int(vip), chat_mode),
        )
        await db.commit()


async def remove_from_queue(user_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM waiting_queue WHERE user_id=?", (user_id,))
        await db.commit()


async def find_and_claim_partner(
    user_id: int, gender_pref: str, own_gender: str, vip: bool, chat_mode: str = "normal"
) -> int | None:
    """
    Атомарно ищет партнёра, удаляет обоих из очереди и создаёт чат.
    Все операции выполняются в одной транзакции с WAL-блокировкой,
    исключая состояние гонки при одновременном поиске.

    Возвращает ID партнёра или None (если подходящего нет).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        # Эксклюзивная транзакция: никакой другой коннект не сможет
        # одновременно изменить очередь или чаты.
        await db.execute("BEGIN EXCLUSIVE")
        try:
            db.row_factory = aiosqlite.Row
            query = """
                SELECT q.user_id FROM waiting_queue q
                WHERE q.user_id != ?
                  AND q.chat_mode = ?
                  AND (? = 'any' OR q.own_gender = ? OR q.own_gender = 'any')
                  AND (q.gender_pref = 'any' OR q.gender_pref = ? OR ? = 'any')
                ORDER BY q.is_vip DESC, q.joined_at ASC
                LIMIT 1
            """
            cur = await db.execute(
                query, (user_id, chat_mode, gender_pref, gender_pref, own_gender, own_gender)
            )
            row = await cur.fetchone()
            if not row:
                await db.execute("ROLLBACK")
                return None

            partner_id = row["user_id"]

            # Удаляем обоих из очереди
            await db.execute(
                "DELETE FROM waiting_queue WHERE user_id IN (?, ?)",
                (user_id, partner_id),
            )
            # Создаём чат (строгий INSERT — не OR REPLACE)
            await db.execute(
                "INSERT INTO active_chats (user1_id, user2_id) VALUES (?, ?)",
                (user_id, partner_id),
            )
            # Счётчики чатов
            await db.execute(
                "UPDATE users SET total_chats=total_chats+1 WHERE user_id IN (?,?)",
                (user_id, partner_id),
            )
            await db.execute("COMMIT")
            return partner_id

        except Exception:
            await db.execute("ROLLBACK")
            raise


async def queue_length() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM waiting_queue")
        row = await cur.fetchone()
        return row[0]


async def is_in_queue(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT 1 FROM waiting_queue WHERE user_id=?", (user_id,))
        return bool(await cur.fetchone())


# ── Активные чаты ────────────────────────────────────────────────────────────

async def create_chat(user1_id: int, user2_id: int) -> None:
    """Создаёт чат напрямую (без очереди). Используйте find_and_claim_partner для поиска."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO active_chats (user1_id, user2_id) VALUES (?, ?)",
            (user1_id, user2_id),
        )
        await db.execute(
            "UPDATE users SET total_chats=total_chats+1 WHERE user_id IN (?,?)",
            (user1_id, user2_id),
        )
        await db.commit()


async def get_partner(user_id: int) -> int | None:
    """Возвращает ID собеседника или None."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT user1_id, user2_id FROM active_chats WHERE user1_id=? OR user2_id=?",
            (user_id, user_id),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return row[1] if row[0] == user_id else row[0]


async def end_chat(user_id: int) -> int | None:
    """Удаляет чат. Возвращает ID партнёра (если был)."""
    partner_id = await get_partner(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM active_chats WHERE user1_id=? OR user2_id=?",
            (user_id, user_id),
        )
        await db.commit()
    return partner_id


async def is_in_chat(user_id: int) -> bool:
    return await get_partner(user_id) is not None


# ── Статистика (для админ-панели) ────────────────────────────────────────────

# ── Анонимные сообщения ───────────────────────────────────────────────────────

async def save_anon_message(
    token: str,
    sender_id: int,
    receiver_id: int,
    content_type: str,
    text: str | None = None,
    file_id: str | None = None,
    caption: str | None = None,
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO anon_messages
               (token, sender_id, receiver_id, content_type, text, file_id, caption)
               VALUES (?,?,?,?,?,?,?)""",
            (token, sender_id, receiver_id, content_type, text, file_id, caption),
        )
        await db.commit()


async def get_anon_message(token: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM anon_messages WHERE token=?", (token,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def mark_replied(token: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE anon_messages SET is_replied=1 WHERE token=?", (token,)
        )
        await db.commit()


async def is_blocked(receiver_id: int, sender_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM anon_blocks WHERE receiver_id=? AND sender_id=?",
            (receiver_id, sender_id),
        )
        return bool(await cur.fetchone())


async def block_sender(receiver_id: int, token: str) -> bool:
    """Блокирует отправителя по токену. Возвращает True если успешно."""
    msg = await get_anon_message(token)
    if not msg:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO anon_blocks (receiver_id, sender_id) VALUES (?,?)",
            (receiver_id, msg["sender_id"]),
        )
        await db.commit()
    return True


async def get_anon_stats(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        recv_cur = await db.execute(
            "SELECT COUNT(*) FROM anon_messages WHERE receiver_id=?", (user_id,)
        )
        repl_cur = await db.execute(
            "SELECT COUNT(*) FROM anon_messages WHERE receiver_id=? AND is_replied=1",
            (user_id,),
        )
        sent_cur = await db.execute(
            "SELECT COUNT(*) FROM anon_messages WHERE sender_id=?", (user_id,)
        )
        return {
            "received": (await recv_cur.fetchone())[0],
            "replied":  (await repl_cur.fetchone())[0],
            "sent":     (await sent_cur.fetchone())[0],
        }


# ── Статистика (для админ-панели) ────────────────────────────────────────────

async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        total_cur   = await db.execute("SELECT COUNT(*) FROM users")
        vip_cur     = await db.execute("SELECT COUNT(*) FROM users WHERE is_vip=1")
        banned_cur  = await db.execute("SELECT COUNT(*) FROM users WHERE is_banned=1")
        chats_cur   = await db.execute("SELECT COUNT(*) FROM active_chats")
        queue_cur   = await db.execute("SELECT COUNT(*) FROM waiting_queue")
        msgs_cur    = await db.execute("SELECT SUM(messages_sent) FROM users")
        revenue_cur = await db.execute("SELECT SUM(stars) FROM payments")

        return {
            "total_users":   (await total_cur.fetchone())[0],
            "vip_users":     (await vip_cur.fetchone())[0],
            "banned_users":  (await banned_cur.fetchone())[0],
            "active_chats":  (await chats_cur.fetchone())[0],
            "in_queue":      (await queue_cur.fetchone())[0],
            "total_messages":(await msgs_cur.fetchone())[0] or 0,
            "total_stars":   (await revenue_cur.fetchone())[0] or 0,
        }


async def get_all_users(limit: int = 50, offset: int = 0) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM users ORDER BY registered_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
