import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from httpx import HTTPError

from bot_client.config import api
from bot_client.helpers import (
    draft_title,
    download_telegram_file,
    guess_content_type,
    show_ready_lesson,
    task_ok,
)
from bot_client.keyboards import materials_keyboard, remove_keyboard, start_keyboard
from bot_client.states import CreateLesson

router = Router(name="create")
logger = logging.getLogger(__name__)


@router.message(StateFilter(None), F.text == "Создать урок")
async def create_lesson_start(message: Message, state: FSMContext):
    await state.set_state(CreateLesson.topic)
    await message.answer(
        "Введи тему урока (topic):",
        reply_markup=remove_keyboard(),
    )


@router.message(CreateLesson.topic, F.text)
async def set_topic(message: Message, state: FSMContext):
    await state.update_data(topic=message.text.strip(), materials=[])
    await state.set_state(CreateLesson.level)
    await message.answer("Введи уровень (например A2):")


@router.message(CreateLesson.level, F.text)
async def set_level(message: Message, state: FSMContext):
    await state.update_data(level=message.text.strip())
    await state.set_state(CreateLesson.materials)
    await message.answer(
        "Пришли материалы (docx/pdf), можно несколько.\n"
        "Когда закончишь — нажми «Готово».",
        reply_markup=materials_keyboard(),
    )


@router.message(CreateLesson.materials, F.text == "Отмена")
async def cancel_create(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено.", reply_markup=start_keyboard())


@router.message(CreateLesson.materials, F.document)
async def collect_documents(
    message: Message,
    state: FSMContext,
    album: list[Message] | None = None,
):
    messages = album or [message]
    data = await state.get_data()
    materials: list[dict] = list(data.get("materials") or [])

    for msg in messages:
        doc = msg.document
        if not doc:
            continue
        materials.append({
            "file_id": doc.file_id,
            "file_name": doc.file_name or f"file_{doc.file_id}.bin",
        })

    await state.update_data(materials=materials)
    await message.answer(
        f"Файлов в заявке: {len(materials)}. Можно добавить ещё или нажать «Готово».",
        reply_markup=materials_keyboard(),
    )


@router.message(CreateLesson.materials, F.text == "Готово")
async def submit_lesson(message: Message, state: FSMContext):
    data = await state.get_data()
    topic = data.get("topic") or ""
    level = data.get("level") or "B1"
    materials = data.get("materials") or []

    if not topic:
        await state.clear()
        await message.answer("Тема пустая. Начни заново: Создать урок")
        return

    await message.answer("Создаю урок и жду генерацию…", reply_markup=remove_keyboard())

    files_payload: list[tuple[str, bytes, str]] = []
    for item in materials:
        content = await download_telegram_file(message, item["file_id"])
        name = item["file_name"]
        files_payload.append((name, content, guess_content_type(name)))

    try:
        created = await api.create_lesson(
            topic=topic,
            level=level,
            files=files_payload,
            teacher_context="Created from Telegram bot",
        )
        lesson_id = created["id"]
        task_id = created["task_id"]
        await state.update_data(lesson_id=lesson_id, task_id=task_id)

        status = await api.wait_task(task_id)
        if not task_ok(status):
            await state.clear()
            await message.answer(
                f"Генерация не удалась: {status.get('status')} {status.get('result')}",
                reply_markup=start_keyboard(),
            )
            return

        lesson = await api.get_lesson(lesson_id)
        await show_ready_lesson(message, state, lesson_id, draft_title(lesson, topic))
    except HTTPError as exc:
        logger.exception("Create lesson API error")
        await state.clear()
        await message.answer(f"Ошибка API: {exc}", reply_markup=start_keyboard())
    except Exception as exc:
        logger.exception("Create lesson failed")
        await state.clear()
        await message.answer(f"Ошибка: {exc}", reply_markup=start_keyboard())
