import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from httpx import HTTPError

from bot_client.config import api
from bot_client.helpers import draft_title, show_ready_lesson, task_ok
from bot_client.keyboards import download_keyboard, remove_keyboard, start_keyboard
from bot_client.states import CreateLesson, RemarkLesson

router = Router(name="remarks")
logger = logging.getLogger(__name__)


@router.message(RemarkLesson.remark, F.text)
async def apply_remark(message: Message, state: FSMContext):
    text = message.text.strip()
    data = await state.get_data()
    lesson_id = data.get("lesson_id")
    if not lesson_id:
        await state.clear()
        await message.answer("Нет активного урока.", reply_markup=start_keyboard())
        return

    await message.answer("Применяю замечания и жду реген…", reply_markup=remove_keyboard())
    try:
        response = await api.remark_lesson(lesson_id=int(lesson_id), remarks=[text])
        task_id = response["task_id"]
        await state.update_data(task_id=task_id)

        status = await api.wait_task(task_id)
        if not task_ok(status):
            await state.set_state(CreateLesson.ready)
            await message.answer(
                f"Реген не удался: {status.get('status')} {status.get('result')}",
                reply_markup=download_keyboard(),
            )
            return

        lesson = await api.get_lesson(int(lesson_id))
        await show_ready_lesson(
            message,
            state,
            int(lesson_id),
            draft_title(lesson, f"Урок #{lesson_id}"),
        )
    except HTTPError as exc:
        logger.exception("Remark API error")
        await state.set_state(CreateLesson.ready)
        await message.answer(f"Ошибка API: {exc}", reply_markup=download_keyboard())
    except Exception as exc:
        logger.exception("Remark failed")
        await state.set_state(CreateLesson.ready)
        await message.answer(f"Ошибка: {exc}", reply_markup=download_keyboard())
