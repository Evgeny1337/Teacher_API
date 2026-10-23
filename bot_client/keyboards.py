from typing import Optional

from aiogram.types import (
    KeyboardButton,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
)


def start_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Создать урок")],
            [KeyboardButton(text="Загрузить эталоны")],
            [KeyboardButton(text="Посмотреть готовые уроки")]
        ],
        resize_keyboard=True,
    )


def materials_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Готово")],
            [KeyboardButton(text="Отмена")],
        ],
        resize_keyboard=True,
    )


def download_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Скачать DOCX", callback_data="download_lesson")],
            [InlineKeyboardButton(text="Внести правки", callback_data="ready_remark")],
            [InlineKeyboardButton(text="Подтвердить урок", callback_data="ready_approve")],
            [InlineKeyboardButton(text="Подтвердить своим файлом", callback_data="ready_file")],
        ]
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def get_lessons_keyboard(lesson_id:int,
                         lesson_count:int,
                         lesson_topic:str,
                         prev_id: Optional[int] = None,
                         next_id: Optional[int] = None) -> InlineKeyboardMarkup:
    keyboard = []
    if lesson_count == 1:
        keyboard.append(
            [InlineKeyboardButton(text="Скачать урок {}".format(lesson_topic), callback_data=f"preview_get_{lesson_id}")],
        )
    else:
        if prev_id:
            keyboard.append(
                [InlineKeyboardButton(text="<=", callback_data=f"preview_prev_{prev_id}")],
            )
        keyboard.append(
            [InlineKeyboardButton(text="Скачать урок {}".format(lesson_topic), callback_data=f"preview_get_{lesson_id}")],
        )
        if next_id:
            keyboard.append(
                [InlineKeyboardButton(text="=>", callback_data=f"preview_next_{next_id}")],
            )
    return InlineKeyboardMarkup(
        inline_keyboard=keyboard,
    )


