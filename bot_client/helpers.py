from pathlib import Path

from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot_client.keyboards import download_keyboard
from bot_client.states import CreateLesson


CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
}


def guess_content_type(filename: str) -> str:
    return CONTENT_TYPES.get(Path(filename).suffix.lower(), "application/octet-stream")


async def download_telegram_file(message: Message, file_id: str) -> bytes:
    file = await message.bot.get_file(file_id)
    buffer = await message.bot.download_file(file.file_path)
    return buffer.read() if hasattr(buffer, "read") else bytes(buffer)


def draft_title(lesson: dict, fallback: str) -> str:
    return (lesson.get("draft") or {}).get("title") or fallback


def task_ok(status: dict) -> bool:
    result = status.get("result") or {}
    return status.get("status") == "SUCCESS" and result.get("ok") is not False


async def show_ready_lesson(
    message: Message,
    state: FSMContext,
    lesson_id: int,
    title: str,
) -> None:
    await state.set_state(CreateLesson.ready)
    await state.update_data(lesson_id=lesson_id)
    await message.answer(
        f"Готово.\nУрок #{lesson_id}\n{title}",
        reply_markup=download_keyboard(),
    )
