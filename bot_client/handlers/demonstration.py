import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message

from bot_client.keyboards import get_lessons_keyboard

router = Router(name="demonstration")
logger = logging.getLogger(__name__)

@router.message(F.text == "Посмотреть готовые уроки")
async def get_demonstration(message: Message):
    await message.answer(text="Выберите урок для просмотра", reply_markup=get_lessons_keyboard(
        lesson_id=2,
        lesson_count=3,
        lesson_topic="test",
        prev_id=1,
        next_id=3,
    ))

@router.callback_query(F.data.startswith("preview_"))
async def preview_lessons(query: CallbackQuery):
    data = query.data.split("_")
    action = data[1]
    match action:
        case "get":
            await query.answer("Здесь загрузка")
        case "prev":
            await query.answer("Назад")
        case "next":
            await query.answer("Вперед")
        case _:
            await query.answer("Такого нет")

