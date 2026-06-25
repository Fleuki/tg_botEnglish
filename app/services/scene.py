import asyncio
import re
from typing import Callable, TypedDict

from app.services.ai import check_user_text
from app.locales import t
from app.services.prompts import language_name

SCENE_LOCATIONS = {
    "en": "London",
    "ru": "Moscow",
    "fr": "Paris",
    "de": "Berlin",
    "es": "Madrid",
    "pt_br": "São Paulo",
    "id": "Jakarta",
}

MAX_SCENE_NOTES = 4

# user_id -> list of OpenAI chat messages (system, user, assistant)
SCENE_HISTORIES: dict[int, list[dict[str, str]]] = {}
# user_id -> target_language code на время сценки
SCENE_TARGET_LANG: dict[int, str] = {}


class SceneDef(TypedDict):
    button_key: str
    get_system_prompt: Callable[[str], str]
    openings: dict[str, str]


def _cafe_system_prompt(target_language: str) -> str:
    code = target_language or "en"
    lang = language_name(code)
    city = SCENE_LOCATIONS.get(code, "a European city")

    return (
        f"You are a friendly barista in a small café in {city}. Stay in role and react "
        f"naturally to what the customer says, keeping the scene moving. Speak only in "
        f"simple, natural {lang}, 1-2 short sentences per reply. The customer is learning "
        f"{lang} — be warm and patient, and never correct or comment on their {lang} "
        f"while in role."
    )


def _airport_system_prompt(target_language: str) -> str:
    code = target_language or "en"
    lang = language_name(code)

    return (
        f"You are a friendly check-in agent at an airport. Stay in role and react "
        f"naturally to what the passenger says, keeping the scene moving. You may ask "
        f"about their ticket, passport, luggage, and seat preference (window or aisle). "
        f"Speak only in simple, natural {lang}, 1-2 short sentences per reply. "
        f"The passenger is learning {lang} — be warm and patient, and never correct "
        f"or comment on their {lang} while in role."
    )


def _hotel_system_prompt(target_language: str) -> str:
    code = target_language or "en"
    lang = language_name(code)

    return (
        f"You are a friendly hotel receptionist at the front desk. Stay in role and react "
        f"naturally to what the guest says, keeping the scene moving. You may ask about "
        f"their reservation or name, how many nights they are staying, hand them a room key, "
        f"and tell them about breakfast. Speak only in simple, natural {lang}, 1-2 short "
        f"sentences per reply. The guest is learning {lang} — be warm and patient, and "
        f"never correct or comment on their {lang} while in role."
    )


def _doctor_system_prompt(target_language: str) -> str:
    code = target_language or "en"
    lang = language_name(code)

    return (
        f"You are a kind doctor at a routine appointment. Stay in role and react naturally "
        f"to what the patient says, keeping the scene moving. You may ask what bothers them, "
        f"how long they have had it, and give simple, reassuring advice. Use a gentle, calm "
        f"tone — do not scare the patient. Speak only in simple, natural {lang}, 1-2 short "
        f"sentences per reply. The patient is learning {lang} — be warm and patient, and "
        f"never correct or comment on their {lang} while in role."
    )


def _interview_system_prompt(target_language: str) -> str:
    code = target_language or "en"
    lang = language_name(code)

    return (
        f"You are a friendly interviewer at a job interview. Stay in role and react "
        f"naturally to what the candidate says, keeping the scene moving. You may ask simple "
        f"questions about them, their experience, and why they want this job. Be encouraging "
        f"and supportive — do not pressure them. Speak only in simple, natural {lang}, "
        f"1-2 short sentences per reply. The candidate is learning {lang} — be warm and "
        f"patient, and never correct or comment on their {lang} while in role."
    )


def _party_system_prompt(target_language: str) -> str:
    code = target_language or "en"
    lang = language_name(code)

    return (
        f"You are a friendly guest at a casual party, meeting someone new. Stay in role "
        f"and react naturally to what they say, keeping the scene moving. You may ask their "
        f"name, what they do, and find common interests — light small talk. Speak only in "
        f"simple, natural {lang}, 1-2 short sentences per reply. They are learning {lang} — "
        f"be warm and patient, and never correct or comment on their {lang} while in role."
    )


def _shopping_system_prompt(target_language: str) -> str:
    code = target_language or "en"
    lang = language_name(code)

    return (
        f"You are a friendly sales assistant in a clothing shop. Stay in role and react "
        f"naturally to what the customer says, keeping the scene moving. You may help them "
        f"choose clothes, ask about size and colour, and suggest trying something on. "
        f"Speak only in simple, natural {lang}, 1-2 short sentences per reply. The customer "
        f"is learning {lang} — be warm and patient, and never correct or comment on their "
        f"{lang} while in role."
    )


def _free_system_prompt(target_language: str) -> str:
    code = target_language or "en"
    lang = language_name(code)

    return (
        f"You are a friendly native {lang} speaker having a casual free conversation with "
        f"someone who is learning {lang}. There is no fixed role or scenario — talk about "
        f"whatever topic they choose. If they have not picked a topic yet, gently suggest "
        f"a couple of easy options (for example hobbies, travel, or their day). Speak only "
        f"in simple, natural {lang}, 1-2 short sentences per reply suited to their level. "
        f"Keep the conversation going, be warm and supportive, and never correct or comment "
        f"on their {lang} during the chat."
    )


SCENES: dict[str, SceneDef] = {
    "cafe": {
        "button_key": "scene_cafe",
        "get_system_prompt": _cafe_system_prompt,
        "openings": {
            "en": "Hi! What can I get for you today?",
            "ru": "Привет! Что для вас приготовить?",
        },
    },
    "airport": {
        "button_key": "scene_airport",
        "get_system_prompt": _airport_system_prompt,
        "openings": {
            "en": "Good morning! May I see your passport and booking, please?",
            "ru": "Добрый день! Можно ваш паспорт и билет, пожалуйста?",
        },
    },
    "hotel": {
        "button_key": "scene_hotel",
        "get_system_prompt": _hotel_system_prompt,
        "openings": {
            "en": "Good evening! Welcome. Do you have a reservation with us?",
            "ru": "Добрый вечер! Добро пожаловать. У вас есть бронь?",
        },
    },
    "doctor": {
        "button_key": "scene_doctor",
        "get_system_prompt": _doctor_system_prompt,
        "openings": {
            "en": "Hello! Please have a seat. What brings you in today?",
            "ru": "Здравствуйте! Присаживайтесь. Что вас беспокоит?",
        },
    },
    "interview": {
        "button_key": "scene_interview",
        "get_system_prompt": _interview_system_prompt,
        "openings": {
            "en": "Hi! Thanks for coming in. Tell me a little about yourself.",
            "ru": "Здравствуйте! Спасибо, что пришли. Расскажите немного о себе.",
        },
    },
    "party": {
        "button_key": "scene_party",
        "get_system_prompt": _party_system_prompt,
        "openings": {
            "en": "Hey! I don't think we've met. I'm Alex — what's your name?",
            "ru": "Привет! Кажется, мы не знакомы. Я Алекс — как тебя зовут?",
        },
    },
    "shopping": {
        "button_key": "scene_shopping",
        "get_system_prompt": _shopping_system_prompt,
        "openings": {
            "en": "Hi there! Can I help you find something today?",
            "ru": "Здравствуйте! Чем могу помочь? Ищете что-то определённое?",
        },
    },
    "free": {
        "button_key": "scene_free",
        "get_system_prompt": _free_system_prompt,
        "openings": {
            "en": (
                "Hi! I'm happy to chat about anything. What's on your mind — "
                "or shall we talk about hobbies, travel, or your day?"
            ),
            "ru": (
                "Привет! Рад поболтать на любую тему. О чём хочешь поговорить — "
                "или может хобби, путешествия или твой день?"
            ),
        },
    },
}


def get_scene_opening(scene_id: str, target_language: str) -> str | None:
    """Готовое приветствие сценки. None — нет шаблона для этого языка (сгенерируем через GPT)."""
    scene = SCENES.get(scene_id, SCENES["cafe"])
    code = target_language or "en"
    return scene["openings"].get(code)


def get_scene_check_context(target_language: str, native_language: str = "Russian") -> str:
    code = target_language or "en"
    lang = language_name(code)

    if code == "en":
        fragment_examples = '"chocolate cake please" or "outside"'
        wrong_lang = "clearly wrong English"
        good_tip = '"тут нужен маленький \'a\'"'
        bad_tip = (
            '"В английском требуется артикль перед исчисляемым существительным"'
        )
        i_override = (
            "CAPITAL 'I' OVERRIDE (overrides any default tip-about-I rule): "
            "NEVER mention capital 'I' by default. Leave tip=\"\" unless the line contains "
            "standalone lowercase 'i' as its own word (e.g. \"i think\", \"can i get\"). "
            "If 'I' is already capital — including I'd, I'm, I'll, I like — stay silent; "
            "do NOT add a tip. "
        )
    elif code == "ru":
        fragment_examples = '"шоколадный торт, пожалуйста" or "на улице"'
        wrong_lang = "clearly wrong Russian"
        good_tip = '"тут нужна буква ё"'
        bad_tip = (
            '"В русском языке требуется использование буквы ё в данном слове"'
        )
        i_override = ""
    else:
        fragment_examples = "short casual fragments"
        wrong_lang = f"clearly wrong {lang}"
        good_tip = "a short friendly hint, written in the student's native language, no jargon"
        bad_tip = "a formal grammar-textbook explanation, or text in any language other than the native one"
        i_override = ""

    return (
        f"This line is from a live role-play scene — a casual spoken-style reply in {lang}, not "
        f"formal writing. Short fragments like {fragment_examples} "
        "are normal and fine; do NOT flag brevity, missing periods, or incomplete "
        f"sentences. Only flag what would genuinely confuse a native speaker or is "
        f"{wrong_lang}. "
        "In 'explanations' rules and in 'tip', explain like a friend — one short plain "
        "sentence in the student's native language, NO grammar jargon. "
        f"Good: {good_tip}. "
        f"Bad: {bad_tip}. "
        "STRICT GROUNDING RULES (must follow): "
        "1) Flag ONLY issues tied to words/symbols that actually appear in THIS line. "
        "Never suggest a fix unrelated to the exact words in this phrase. "
        "2) If the line has no real error, do NOT invent one. Leave has_errors=false, "
        "tip=\"\", explanations=[]. Silence is better than a false note. "
        "3) Before any note: verify the wrong fragment (or the letter/word you mention) "
        "is really present in the line. If not — drop that note entirely. "
        "4) The student's line is the ONLY source of truth — never rely on \"typical\" "
        "mistakes. Before any note, verify the exact wrong fragment appears in the line "
        "in that exact form (case-sensitive). "
        f"{i_override}"
        "Every 'wrong' field must be an exact case-sensitive substring of the student's line. "
        f"LANGUAGE OF EXPLANATIONS (critical): every 'rule', 'tip' and 'praise' MUST be written "
        f"entirely in {native_language}, the student's native language. This applies to ALL notes "
        f"without exception, even though the student's line itself is in {lang}. Do NOT switch to "
        f"{lang} or any other language for the explanations. If you start an explanation, finish it "
        f"in {native_language}."
    )


def is_scene_active(user_id: int) -> bool:
    return user_id in SCENE_HISTORIES


def start_scene(
    user_id: int,
    target_language: str = "en",
    scene_id: str = "cafe",
) -> list[dict[str, str]]:
    scene = SCENES.get(scene_id, SCENES["cafe"])
    code = target_language or "en"
    SCENE_TARGET_LANG[user_id] = code
    history: list[dict[str, str]] = [
        {"role": "system", "content": scene["get_system_prompt"](code)},
    ]
    opening = get_scene_opening(scene_id, code)
    if opening:
        history.append({"role": "assistant", "content": opening})
    SCENE_HISTORIES[user_id] = history
    return history


def apply_scene_opening(user_id: int, opening: str) -> None:
    """Сохраняет первую реплику персонажа в историю сценки."""
    history = SCENE_HISTORIES.get(user_id)
    if not history:
        return
    if history and history[-1]["role"] == "assistant":
        history[-1]["content"] = opening
    else:
        history.append({"role": "assistant", "content": opening})


def stop_scene(user_id: int) -> None:
    SCENE_HISTORIES.pop(user_id, None)
    SCENE_TARGET_LANG.pop(user_id, None)


def _fragment_in_line(fragment: str, line: str) -> bool:
    fragment = fragment.strip()
    if not fragment:
        return False
    return fragment in line


def _has_lowercase_i_pronoun(line: str) -> bool:
    return bool(re.search(r"(?<![A-Za-z])i(?![A-Za-z])", line))


def _tip_about_capital_i(tip: str) -> bool:
    tip_lower = tip.lower()
    if not re.search(r"['\"]?i['\"]?", tip_lower):
        return False
    return any(
        word in tip_lower
        for word in (
            "заглавн", "больш", "capital", "letter", "букв", "always", "всегда",
            "with a capital", "с большой",
        )
    )


def _note_is_grounded(original: str, result: dict, target_language: str = "en") -> bool:
    for explanation in result.get("explanations") or []:
        wrong = explanation.get("wrong", "")
        if not _fragment_in_line(wrong, original):
            return False
        if (target_language or "en") == "en" and wrong.strip() == "i":
            if not _has_lowercase_i_pronoun(original):
                return False

    tip = (result.get("tip") or "").strip()
    if (
        (target_language or "en") == "en"
        and tip
        and _tip_about_capital_i(tip)
        and not _has_lowercase_i_pronoun(original)
    ):
        return False

    corrected = (result.get("corrected") or original).strip()
    if corrected != original and not result.get("has_errors") and not tip:
        return False

    if result.get("has_errors") and not (result.get("explanations") or []):
        if not tip and corrected == original:
            return False

    return True


def _scene_note(
    original: str,
    result: dict,
    target_language: str = "en",
    *,
    natural_hint: str = "",
) -> str | None:
    if not _note_is_grounded(original, result, target_language):
        return None

    tip = (result.get("tip") or "").strip()
    corrected = (result.get("corrected") or original).strip()

    if result.get("has_errors"):
        explanations = result.get("explanations") or []
        if explanations:
            e = explanations[0]
            return f"{e['wrong']} → {e['right']}\n{e['rule']}"
        if tip:
            if corrected != original:
                return f"{original} → {corrected}\n{tip}"
            return f"{original}\n{tip}"
        if corrected != original:
            return f"{original} → {corrected}\n{natural_hint}"
        return None

    if tip:
        if corrected != original:
            return f"{original} → {corrected}\n{tip}"
        return f"{original}\n{tip}"
    return None


def _note_dedup_key(note: str) -> str:
    parts = note.split("\n", 1)
    if len(parts) > 1 and parts[1].strip():
        return parts[1].strip().lower()
    return parts[0].strip().lower()


async def build_scene_recap(
    history: list[dict[str, str]],
    native_language: str,
    target_language: str = "en",
    interface_lang: str = "en",
) -> str | None:
    """Проверяет реплики пользователя и собирает короткий разбор сценки."""
    user_lines = [m["content"] for m in history if m["role"] == "user"]
    if not user_lines:
        return None

    scene_context = get_scene_check_context(target_language, native_language)
    results = await asyncio.gather(
        *(
            check_user_text(
                line,
                native_language,
                target_language=target_language,
                context=scene_context,
            )
            for line in user_lines
        )
    )

    natural_hint = t("scene_note_natural", interface_lang)
    notes: list[tuple[int, str]] = []
    seen_keys: set[str] = set()
    for line, result in zip(user_lines, results):
        if result.get("_error"):
            continue
        note = _scene_note(line, result, target_language, natural_hint=natural_hint)
        if not note:
            continue
        dedup_key = _note_dedup_key(note)
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)
        priority = 0 if result.get("has_errors") else 1
        notes.append((priority, note))

    if not notes:
        return (
            f"{t('scene_recap_title', interface_lang)}\n\n"
            f"{t('scene_recap_all_good', interface_lang)}"
        )

    notes.sort(key=lambda item: item[0])
    body = "\n\n".join(note for _, note in notes[:MAX_SCENE_NOTES])
    return f"{t('scene_recap_title', interface_lang)}\n\n{body}"
