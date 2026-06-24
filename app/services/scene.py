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
    "4) The student's line is the ONLY source of truth — never rely on \"typical\" "
    "mistakes. Before any note, verify the exact wrong fragment appears in the line "
    "in that exact form (case-sensitive). "
    "CAPITAL 'I' OVERRIDE (overrides any default tip-about-I rule): "
    "NEVER mention capital 'I' by default. Leave tip=\"\" unless the line contains "
    "standalone lowercase 'i' as its own word (e.g. \"i think\", \"can i get\"). "
    "If 'I' is already capital — including I'd, I'm, I'll, I like — stay silent; "
    "do NOT add a tip. "
    "Every 'wrong' field must be an exact case-sensitive substring of the student's line."
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


def _note_is_grounded(original: str, result: dict) -> bool:
    for explanation in result.get("explanations") or []:
        wrong = explanation.get("wrong", "")
        if not _fragment_in_line(wrong, original):
            return False
        if wrong.strip() == "i" and not _has_lowercase_i_pronoun(original):
            return False

    tip = (result.get("tip") or "").strip()
    if tip and _tip_about_capital_i(tip) and not _has_lowercase_i_pronoun(original):
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


def _note_dedup_key(note: str) -> str:
    parts = note.split("\n", 1)
    if len(parts) > 1 and parts[1].strip():
        return parts[1].strip().lower()
    return parts[0].strip().lower()


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
    seen_keys: set[str] = set()
    for line, result in zip(user_lines, results):
        if result.get("_error"):
            continue
        note = _scene_note(line, result)
        if not note:
            continue
        dedup_key = _note_dedup_key(note)
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)
        priority = 0 if result.get("has_errors") else 1
        notes.append((priority, note))

    if not notes:
        return "Разбор сценки ✏️\n\nОтлично, тебя везде поняли! 👏"

    notes.sort(key=lambda item: item[0])
    body = "\n\n".join(note for _, note in notes[:MAX_SCENE_NOTES])
    return f"Разбор сценки ✏️\n\n{body}"
