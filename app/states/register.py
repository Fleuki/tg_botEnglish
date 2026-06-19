from aiogram.fsm.state import State, StatesGroup


class RegisterState(StatesGroup):
    interface_language = State()
    native_language = State()
    level = State()
    lesson_time = State()