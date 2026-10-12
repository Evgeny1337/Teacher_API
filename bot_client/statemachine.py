from aiogram.fsm.state import StatesGroup, State


class CreateLesson(StatesGroup):
    topic = State()
    level = State()
    materials = State()
    ready = State()
