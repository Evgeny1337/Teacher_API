import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot_client.config import TOKEN
from bot_client.handlers import build_root_router
from bot_client.middleware import AlbumMiddleware

logging.basicConfig(level=logging.INFO)


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(AlbumMiddleware(latency=0.6))
    dp.include_router(build_root_router())
    return dp


async def main() -> None:
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    bot = Bot(token=TOKEN)
    await create_dispatcher().start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
