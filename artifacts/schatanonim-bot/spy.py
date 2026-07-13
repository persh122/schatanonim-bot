"""
Глобальное состояние режима наблюдения и входа в чаты.
Хранится в памяти — сбрасывается при перезапуске бота.
"""

# Множество admin_id, у которых включён глобальный режим наблюдения
_active: set[int] = set()

# admin_id → (user1_id, user2_id)  — в каком чате сейчас сидит админ
_joined: dict[int, tuple[int, int]] = {}


# ── Глобальное наблюдение ────────────────────────────────────────────────────

def enable(admin_id: int) -> None:
    _active.add(admin_id)


def disable(admin_id: int) -> None:
    _active.discard(admin_id)


def toggle(admin_id: int) -> bool:
    """Переключает режим. Возвращает True если теперь включён."""
    if admin_id in _active:
        _active.discard(admin_id)
        return False
    else:
        _active.add(admin_id)
        return True


def is_active(admin_id: int) -> bool:
    return admin_id in _active


def all_active() -> set[int]:
    return set(_active)


# ── Вход в конкретный чат ────────────────────────────────────────────────────

def join_chat(admin_id: int, user1_id: int, user2_id: int) -> None:
    _joined[admin_id] = (user1_id, user2_id)


def leave_chat(admin_id: int) -> None:
    _joined.pop(admin_id, None)


def get_joined_chat(admin_id: int) -> tuple[int, int] | None:
    return _joined.get(admin_id)


def admins_in_chat(user1_id: int, user2_id: int) -> list[int]:
    """Возвращает список admin_id, которые вошли в этот чат."""
    pair = {user1_id, user2_id}
    result = []
    for aid, (u1, u2) in _joined.items():
        if {u1, u2} == pair:
            result.append(aid)
    # Добавляем глобальных наблюдателей
    for aid in _active:
        if aid not in result:
            result.append(aid)
    return result


def is_in_any_chat(admin_id: int) -> bool:
    return admin_id in _joined
