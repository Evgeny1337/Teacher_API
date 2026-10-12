import asyncio
from collections import defaultdict
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject


class AlbumMiddleware(BaseMiddleware):
    def __init__(self, latency: float = 0.6):
        self.latency = latency
        self._albums: dict[str, list[Message]] = {}
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message) or not event.media_group_id:
            return await handler(event, data)

        group_id = event.media_group_id
        async with self._locks[group_id]:
            is_first = group_id not in self._albums
            if is_first:
                self._albums[group_id] = [event]
            else:
                self._albums[group_id].append(event)

        if not is_first:
            return None

        await asyncio.sleep(self.latency)
        album = self._albums.pop(group_id, [event])
        self._locks.pop(group_id, None)
        data["album"] = album
        return await handler(event, data)
