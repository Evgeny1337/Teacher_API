import asyncio
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from dotenv import load_dotenv
from httpx import HTTPError

from bot_client.api import TeacherApiClient
from bot_client.keyboards import (
    start_keyboard,
    materials_keyboard,
    download_keyboard,
    remove_keyboard,
)
from bot_client.middleware import AlbumMiddleware
from bot_client.statemachine import CreateLesson, RemarkLesson, ApproveFile

load_dotenv(override=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BOT_SHARED_SECRET = os.getenv("BOT_SHARED_SECRET", "test")
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

dp = Dispatcher(storage=MemoryStorage())
dp.message.middleware(AlbumMiddleware(latency=0.6))
api = TeacherApiClient(API_BASE_URL, BOT_SHARED_SECRET)


def _guess_content_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
    }.get(suffix, "application/octet-stream")


async def _show_ready_lesson(message: Message, state: FSMContext, lesson_id: int, title: str):
    await state.set_state(CreateLesson.ready)
    await state.update_data(lesson_id=lesson_id)
    await message.answer(
        f"Готово.\nУрок #{lesson_id}\n{title}",
        reply_markup=download_keyboard(),
    )


@dp.message(CommandStart())
async def command_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Выбери действие", reply_markup=start_keyboard())


@dp.message(StateFilter(None), F.text == "Создать урок")
async def create_lesson_start(message: Message, state: FSMContext):
    await state.set_state(CreateLesson.topic)
    await message.answer(
        "Введи тему урока (topic):",
        reply_markup=remove_keyboard(),
    )


@dp.message(CreateLesson.topic, F.text)
async def set_topic(message: Message, state: FSMContext):
    await state.update_data(topic=message.text.strip(), materials=[])
    await state.set_state(CreateLesson.level)
    await message.answer("Введи уровень (например A2):")


@dp.message(CreateLesson.level, F.text)
async def set_level(message: Message, state: FSMContext):
    await state.update_data(level=message.text.strip())
    await state.set_state(CreateLesson.materials)
    await message.answer(
        "Пришли материалы (docx/pdf), можно несколько.\n"
        "Когда закончишь — нажми «Готово».",
        reply_markup=materials_keyboard(),
    )


@dp.message(CreateLesson.materials, F.text == "Отмена")
async def cancel_create(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено.", reply_markup=start_keyboard())


@dp.message(CreateLesson.materials, F.document)
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


@dp.message(CreateLesson.materials, F.text == "Готово")
async def submit_lesson(message: Message, state: FSMContext):
    data = await state.get_data()
    topic = data.get("topic") or ""
    level = data.get("level") or "B1"
    materials = data.get("materials") or []

    if not topic:
        await message.answer("Тема пустая. Начни заново: Создать урок")
        await state.clear()
        return

    await message.answer("Создаю урок и жду генерацию…", reply_markup=remove_keyboard())

    files_payload: list[tuple[str, bytes, str]] = []
    for item in materials:
        file = await message.bot.get_file(item["file_id"])
        buffer = await message.bot.download_file(file.file_path)
        content = buffer.read() if hasattr(buffer, "read") else bytes(buffer)
        name = item["file_name"]
        files_payload.append((name, content, _guess_content_type(name)))

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
        result = status.get("result") or {}
        if status.get("status") != "SUCCESS" or result.get("ok") is False:
            await state.clear()
            await message.answer(
                f"Генерация не удалась: {status.get('status')} {result}",
                reply_markup=start_keyboard(),
            )
            return

        lesson = await api.get_lesson(lesson_id)
        title = (lesson.get("draft") or {}).get("title") or topic
        await _show_ready_lesson(message, state, lesson_id, title)
    except HTTPError as exc:
        logger.exception("API error")
        await state.clear()
        await message.answer(f"Ошибка API: {exc}", reply_markup=start_keyboard())
    except Exception as exc:
        logger.exception("Submit failed")
        await state.clear()
        await message.answer(f"Ошибка: {exc}", reply_markup=start_keyboard())


@dp.message(RemarkLesson.remark, F.text)
async def remark_lesson(message: Message, state: FSMContext):
    text = message.text.strip()
    data = await state.get_data()
    lesson_id = data.get("lesson_id")
    if not lesson_id:
        await state.clear()
        await message.answer("Нет активного урока.", reply_markup=start_keyboard())
        return

    await message.answer("Применяю замечания и жду реген…", reply_markup=remove_keyboard())
    try:
        remark_response = await api.remark_lesson(
            lesson_id=int(lesson_id),
            remarks=[text],
        )
        task_id = remark_response["task_id"]
        await state.update_data(task_id=task_id)

        status = await api.wait_task(task_id)
        result = status.get("result") or {}
        if status.get("status") != "SUCCESS" or result.get("ok") is False:
            await state.set_state(CreateLesson.ready)
            await message.answer(
                f"Реген не удался: {status.get('status')} {result}",
                reply_markup=download_keyboard(),
            )
            return

        lesson = await api.get_lesson(int(lesson_id))
        title = (lesson.get("draft") or {}).get("title") or f"Урок #{lesson_id}"
        await _show_ready_lesson(message, state, int(lesson_id), title)
    except HTTPError as exc:
        logger.exception("Remark API error")
        await state.set_state(CreateLesson.ready)
        await message.answer(f"Ошибка API: {exc}", reply_markup=download_keyboard())
    except Exception as exc:
        logger.exception("Remark failed")
        await state.set_state(CreateLesson.ready)
        await message.answer(f"Ошибка: {exc}", reply_markup=download_keyboard())


@dp.message(ApproveFile.file, F.document)
async def approve_lesson_with_file(message: Message, state: FSMContext):
    data = await state.get_data()
    lesson_id = data.get("lesson_id")
    doc = message.document
    if not lesson_id or not doc:
        await state.set_state(CreateLesson.ready)
        await message.answer("Нет урока или файла.", reply_markup=download_keyboard())
        return

    try:
        file = await message.bot.get_file(doc.file_id)
        buffer = await message.bot.download_file(file.file_path)
        content = buffer.read() if hasattr(buffer, "read") else bytes(buffer)
        filename = doc.file_name or f"final_{lesson_id}.docx"

        await api.approve_lesson_with_file(
            int(lesson_id),
            filename=filename,
            content=content,
            content_type=doc.mime_type or _guess_content_type(filename),
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


@dp.callback_query(CreateLesson.ready, F.data.startswith("ready_"))
async def ready_actions(query: CallbackQuery, state: FSMContext):
    await query.answer()
    postfix = (query.data or "").removeprefix("ready_")
    data = await state.get_data()
    lesson_id = data.get("lesson_id")
    if not lesson_id:
        await query.message.answer("Нет активного урока.", reply_markup=start_keyboard())
        return

    if postfix == "remark":
        await state.set_state(RemarkLesson.remark)
        await state.update_data(lesson_id=lesson_id)
        await query.message.answer(
            "Напиши замечания одним сообщением.",
            reply_markup=remove_keyboard(),
        )
        return

    if postfix == "approve":
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
        return

    if postfix == "file":
        await state.set_state(ApproveFile.file)
        await state.update_data(lesson_id=lesson_id)
        await query.message.answer(
            "Пришли итоговый файл урока (docx/pdf).",
            reply_markup=remove_keyboard(),
        )


@dp.callback_query(F.data == "download_lesson")
async def callback_download(query: CallbackQuery, state: FSMContext):
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


@dp.message(F.text == "Загрузить эталоны")
async def references_stub(message: Message):
    await message.answer("Пока не реализовано. Скоро добавим загрузку эталонов.")


async def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    bot = Bot(token=TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
