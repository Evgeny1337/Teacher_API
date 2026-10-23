from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot_client.keyboards import start_keyboard

router = Router(name="start")


@router.message(CommandStart())
async def command_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Выбери действие", reply_markup=start_keyboard())


@router.message(F.text == "Загрузить эталоны")
async def references_stub(message: Message):
    await message.answer("Пока не реализовано. Скоро добавим загрузку эталонов.")

