"""
Глобальное состояние режима наблюдения.
Хранится в памяти — сбрасывается при перезапуске бота.
"""

# Множество admin_id, у которых включён режим наблюдения
_active: set[int] = set()


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
