from aiogram import Router

from bot_client.handlers.approve import router as approve_router
from bot_client.handlers.create import router as create_router
from bot_client.handlers.ready import router as ready_router
from bot_client.handlers.remarks import router as remarks_router
from bot_client.handlers.start import router as start_router
from bot_client.handlers.demonstration import router as demonstration_router


def build_root_router() -> Router:
    root = Router()
    root.include_router(start_router)
    root.include_router(create_router)
    root.include_router(ready_router)
    root.include_router(remarks_router)
    root.include_router(approve_router)
    root.include_router(demonstration_router)
    return root
