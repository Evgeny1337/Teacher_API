import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery
from httpx import HTTPError

from bot_client.config import api
from bot_client.keyboards import download_keyboard, remove_keyboard, start_keyboard
from bot_client.states import ApproveFile, CreateLesson, RemarkLesson

router = Router(name="ready")
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "download_lesson")
async def download_lesson(query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lesson_id = data.get("lesson_id")
    if not lesson_id:
        await query.answer("Нет активного урока", show_alert=True)
        return

    await query.answer("Готовлю файл…")
    try:
        content = await api.download_lesson_docx(int(lesson_id))
        document = BufferedInputFile(content, filename=f"lesson_{lesson_id}.docx")
        await query.message.answer_document(document)
    except HTTPError as exc:
        await query.message.answer(f"Не удалось скачать DOCX: {exc}")


@router.callback_query(CreateLesson.ready, F.data == "ready_remark")
async def ready_remark(query: CallbackQuery, state: FSMContext):
    await query.answer()
    data = await state.get_data()
    lesson_id = data.get("lesson_id")
    if not lesson_id:
        await query.message.answer("Нет активного урока.", reply_markup=start_keyboard())
        return

    await state.set_state(RemarkLesson.remark)
    await state.update_data(lesson_id=lesson_id)
    await query.message.answer(
        "Напиши замечания одним сообщением.",
        reply_markup=remove_keyboard(),
    )


@router.callback_query(CreateLesson.ready, F.data == "ready_approve")
async def ready_approve(query: CallbackQuery, state: FSMContext):
    await query.answer()
    data = await state.get_data()
    lesson_id = data.get("lesson_id")
    if not lesson_id:
        await query.message.answer("Нет активного урока.", reply_markup=start_keyboard())
        return

    try:
        lesson = await api.get_lesson(int(lesson_id))
        draft = lesson.get("draft")
        if not draft:
            await query.message.answer("У урока нет draft.", reply_markup=download_keyboard())
            return
        await api.approve_lesson(int(lesson_id), draft=draft)
        await state.clear()
        await query.message.answer(
            f"Урок #{lesson_id} утверждён и добавлен в Style RAG.",
            reply_markup=start_keyboard(),
        )
    except HTTPError as exc:
        logger.exception("Approve API error")
        await query.message.answer(f"Ошибка API: {exc}", reply_markup=download_keyboard())


@router.callback_query(CreateLesson.ready, F.data == "ready_file")
async def ready_file(query: CallbackQuery, state: FSMContext):
    await query.answer()
    data = await state.get_data()
    lesson_id = data.get("lesson_id")
    if not lesson_id:
        await query.message.answer("Нет активного урока.", reply_markup=start_keyboard())
        return

    await state.set_state(ApproveFile.file)
    await state.update_data(lesson_id=lesson_id)
    await query.message.answer(
        "Пришли итоговый файл урока (docx/pdf).",
        reply_markup=remove_keyboard(),
    )
