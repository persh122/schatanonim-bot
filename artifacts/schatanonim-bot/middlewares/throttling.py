"""
Middleware для ограничения частоты сообщений (антиспам).
"""

import time
from typing import Any, Callable, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message


class ThrottlingMiddleware(BaseMiddleware):
    """Блокирует пользователей, отправляющих сообщения слишком часто."""

    def __init__(self, rate_limit: float = 0.5):
        """
        :param rate_limit: минимальный интервал между сообщениями в секундах
        """
        self.rate_limit = rate_limit
        self._last_time: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        user = event.from_user
        if not user:
            return await handler(event, data)

        now = time.monotonic()
        last = self._last_time.get(user.id, 0)

        if now - last < self.rate_limit:
            # Слишком быстро — молча игнорируем
            return None

        self._last_time[user.id] = now
        return await handler(event, data)
