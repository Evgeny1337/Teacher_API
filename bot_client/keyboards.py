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
