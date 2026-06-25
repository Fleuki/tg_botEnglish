from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.locales import t
from app.services.scene import SCENES


def scenes_menu_kb(lang: str):
    kb = InlineKeyboardBuilder()
    for scene_id in SCENES:
        kb.button(
            text=t(SCENES[scene_id]["button_key"], lang),
            callback_data=f"scene:pick:{scene_id}",
        )
    kb.adjust(1)
    return kb.as_markup()


def scene_active_kb(lang: str = "en"):
    kb = InlineKeyboardBuilder()
    kb.button(text=t("scene_stop_button", lang), callback_data="scene:stop")
    kb.adjust(1)
    return kb.as_markup()
