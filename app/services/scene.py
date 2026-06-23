import asyncio
import re

from app.services.ai import check_user_text

SCENE_SYSTEM_PROMPT = (
    "You are a friendly barista in a small London café. Stay in role and react "
    "naturally to what the customer says, keeping the scene moving. Speak only in "
    "simple, natural English, 1-2 short sentences per reply. The customer is learning "
    "English — be warm and patient, and never correct or comment on their English "
    "while in role."
)

BARISTA_OPENING = "Hi! What can I get for you today?"

SCENE_CHECK_CONTEXT = (
    "This line is from a live café role-play — a casual spoken-style reply, not "
    "formal writing. Short fragments like \"chocolate cake please\" or \"outside\" "
    "are normal and fine; do NOT flag brevity, missing periods, or incomplete "
    "sentences. Only flag what would genuinely confuse a native speaker or is "
    "clearly wrong English. "
    "In 'explanations' rules and in 'tip', explain like a friend — one short plain "
    "sentence in the student's native language, NO grammar jargon (no 'article', "
    "'countable noun', 'preposition', 'singular', etc.). "
    "Good: \"тут нужен маленький 'a'\". "
    "Bad: \"В английском требуется артикль перед исчисляемым существительным\". "
    "STRICT GROUNDING RULES (must follow): "
    "1) Flag ONLY issues tied to words/symbols that actually appear in THIS line. "
    "Never suggest a fix unrelated to the exact words in this phrase. "
    "2) If the line has no real error, do NOT invent one. Leave has_errors=false, "
    "tip=\"\", explanations=[]. Silence is better than a false note. "
    "3) Before any note: verify the wrong fragment (or the letter/word you mention) "
    "is really present in the line. If not — drop that note entirely. "
    "4) Do not mention rules that do not apply (e.g. never mention capital 'I' "
    "unless the pronoun 'I' actually appears in the line). "
    "Every 'wrong' field must be an exact substring of the student's line."
)

MAX_SCENE_NOTES = 4

# user_id -> list of OpenAI chat messages (system, user, assistant)
SCENE_HISTORIES: dict[int, list[dict[str, str]]] = {}


def is_scene_active(user_id: int) -> bool:
    return user_id in SCENE_HISTORIES


def start_scene(user_id: int) -> list[dict[str, str]]:
    history = [
        {"role": "system", "content": SCENE_SYSTEM_PROMPT},
        {"role": "assistant", "content": BARISTA_OPENING},
    ]
    SCENE_HISTORIES[user_id] = history
    return history


def stop_scene(user_id: int) -> None:
    SCENE_HISTORIES.pop(user_id, None)


def _fragment_in_line(fragment: str, line: str) -> bool:
    fragment = fragment.strip()
    if not fragment:
        return False
    return fragment.lower() in line.lower()


def _tip_about_capital_i(tip: str) -> bool:
    tip_lower = tip.lower()
    if not re.search(r"['\"]?i['\"]?", tip_lower):
        return False
    return any(
        word in tip_lower
        for word in ("заглавн", "больш", "capital", "letter", "букв", "always", "всегда")
    )


def _note_is_grounded(original: str, result: dict) -> bool:
    for explanation in result.get("explanations") or []:
        if not _fragment_in_line(explanation.get("wrong", ""), original):
            return False

    tip = (result.get("tip") or "").strip()
    if tip and _tip_about_capital_i(tip) and not re.search(r"\bi\b", original, re.IGNORECASE):
        return False

    corrected = (result.get("corrected") or original).strip()
    if corrected != original and not result.get("has_errors") and not tip:
        return False

    if result.get("has_errors") and not (result.get("explanations") or []):
        if not tip and corrected == original:
            return False

    return True


def _scene_note(original: str, result: dict) -> str | None:
    if not _note_is_grounded(original, result):
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
            return f"{original} → {corrected}\nтак звучит естественнее"
        return None

    if tip:
        if corrected != original:
            return f"{original} → {corrected}\n{tip}"
        return f"{original}\n{tip}"
    return None


async def build_scene_recap(history: list[dict[str, str]], native_language: str) -> str | None:
    """Проверяет реплики пользователя и собирает короткий разбор сценки."""
    user_lines = [m["content"] for m in history if m["role"] == "user"]
    if not user_lines:
        return None

    results = await asyncio.gather(
        *(
            check_user_text(line, native_language, context=SCENE_CHECK_CONTEXT)
            for line in user_lines
        )
    )

    notes: list[tuple[int, str]] = []
    for line, result in zip(user_lines, results):
        if result.get("_error"):
            continue
        note = _scene_note(line, result)
        if note:
            priority = 0 if result.get("has_errors") else 1
            notes.append((priority, note))

    if not notes:
        return "Разбор сценки ✏️\n\nОтлично, тебя везде поняли! 👏"

    notes.sort(key=lambda item: item[0])
    body = "\n\n".join(note for _, note in notes[:MAX_SCENE_NOTES])
    return f"Разбор сценки ✏️\n\n{body}"
