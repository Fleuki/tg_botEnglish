from aiogram.fsm.state import State, StatesGroup


class RegisterState(StatesGroup):
    interface_language = State()
    native_language = State()
    level = State()
    lesson_time = State()


# Отдельные состояния для изменения ОДНОГО параметра через настройки.
# Нужны чтобы отличать "идёт регистрация" от "пользователь меняет только время".
class SettingsState(StatesGroup):
    edit_native_language = State()
    edit_lesson_time = State()