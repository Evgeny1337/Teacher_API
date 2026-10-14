import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from httpx import HTTPError

from bot_client.config import api
from bot_client.helpers import download_telegram_file, guess_content_type
from bot_client.keyboards import download_keyboard, start_keyboard
from bot_client.states import ApproveFile, CreateLesson

router = Router(name="approve")
logger = logging.getLogger(__name__)


@router.message(ApproveFile.file, F.document)
async def approve_with_file(message: Message, state: FSMContext):
    data = await state.get_data()
    lesson_id = data.get("lesson_id")
    doc = message.document
    if not lesson_id or not doc:
        await state.set_state(CreateLesson.ready)
        await message.answer("Нет урока или файла.", reply_markup=download_keyboard())
        return

    try:
        content = await download_telegram_file(message, doc.file_id)
        filename = doc.file_name or f"final_{lesson_id}.docx"
        await api.approve_lesson_with_file(
            int(lesson_id),
            filename=filename,
            content=content,
            content_type=doc.mime_type or guess_content_type(filename),
        )
        await state.clear()
        await message.answer(
            f"Урок #{lesson_id} утверждён (файл) и добавлен в Style RAG.",
            reply_markup=start_keyboard(),
        )
    except HTTPError as exc:
        logger.exception("Approve file API error")
        await state.set_state(CreateLesson.ready)
        await message.answer(f"Ошибка API: {exc}", reply_markup=download_keyboard())
    except Exception as exc:
        logger.exception("Approve file failed")
        await state.set_state(CreateLesson.ready)
        await message.answer(f"Ошибка: {exc}", reply_markup=download_keyboard())
