import os
import json
import asyncio
import logging
import re
from app.services.topics import pick_topic
from openai import AsyncOpenAI
from sqlalchemy import select
from app.database.db import AsyncSessionLocal
from app.database.models.ai_cache import AICache
from app.services.cache import make_prompt_hash
client = AsyncOpenAI(api_key=os.getenv("AI_TUNNEL_API_KEY"),
    base_url="https://api.aitunnel.ru/v1")
from app.database.models.user import User
from app.services.prompts import get_system_prompt, language_name
from app.services.cache import make_prompt_hash, get_cache, set_cache
# -------------------------
# FALLBACK (обязательно)
# -------------------------
FALLBACK_LESSON = {
    "title": "Daily Lesson",

    "text": """
Hello! My name is Anna.

I live in London.
I work in an office.
Every morning I drink coffee.

On weekends I meet my friends.
""",

    "translation": """
Привет! Меня зовут Анна.

Я живу в Лондоне.
Я работаю в офисе.
Каждое утро я пью кофе.

По выходным я встречаюсь с друзьями.
""",

    "questions": [
        {
            "question": "Where does Anna live?",
            "answer": "In London"
        },
        {
            "question": "What does Anna drink every morning?",
            "answer": "Coffee"
        }
    ],

    "vocab": [
        {
            "word": "office",
            "translation": "офис"
        },
        {
            "word": "coffee",
            "translation": "кофе"
        },
        {
            "word": "friends",
            "translation": "друзья"
        }
    ]
}

LEVEL_RULES = {
    "A1": {
        "vocab": "very simple daily words (food, family, home, school)",
        "story": "5-6 sentences, very simple grammar, present tense mostly",
        "topics": ["home", "family", "school", "food", "daily routine"],
        "must_include": []
    },

    "A2": {
        "vocab": "basic everyday actions and objects",
        "story": "6-7 sentences, past + present simple",
        "topics": ["shopping", "travel", "friends", "weekend", "school life"],
        "must_include": []
    },

    "B1": {
        "vocab": "intermediate natural vocabulary",
        "story": "7-9 sentences, mixed tenses",
        "topics": ["job interview", "travel problem", "moving", "friend conflict", "work experience"],
        "must_include": [
            "problem or conflict",
            "decision making",
            "unexpected event OR change",
        ]
    },

    "B2": {
        "vocab": "advanced vocabulary and expressions",
        "story": "8-10 sentences, complex grammar",
        "topics": ["career change", "social issues", "technology", "studies abroad"],
        "must_include": [
            "opinion or argument",
            "comparison",
            "complex situation",
        ]
    }
    
}

# -------------------------
# CONFIG
# -------------------------
MAX_RETRIES = 3
BASE_DELAY = 2  # seconds

# -------------------------
# MAIN FUNCTION
# -------------------------



async def generate_ai_lesson(user: User) -> dict:
    topic = pick_topic(user)
    target_code = user.target_language or "en"
    target_lang = language_name(target_code)

    # 🔥 ОДИН ЕДИНЫЙ CACHE KEY
    cache_key = make_prompt_hash(user, topic)

    # ----------------------
    # 1. RAM CACHE
    # ----------------------
    cached = get_cache(cache_key)
    if cached:
        print("⚡ RAM CACHE HIT")
        return cached

    user_prompt = f"""
Target language (language being learned): {target_lang}
CEFR level in {target_lang}: {user.level}

User native language (for translations only):
{user.native_language}

Topic:
{topic}

Create:

1. A title in {target_lang}.
2. A text of 7-10 sentences in {target_lang}.
3. Full translation of the text into {user.native_language}.
4. EXACTLY 3 comprehension questions in {target_lang}.
5. 4-5 vocabulary words from the text (words in {target_lang}).
6. Vocabulary translations must be in {user.native_language}.
7. Do NOT use any other language for translations.
Return JSON only.

IMPORTANT:
- The lesson text and questions must be in {target_lang}.
- Vocabulary translations must be in the same language as the full translation ({user.native_language}).

"""

    prompt_hash = make_prompt_hash(user, topic)

    # ----------------------
    # 2. DB CACHE
    # ----------------------
    async with AsyncSessionLocal() as session:
        cached_db = await session.execute(
            select(AICache).where(
                AICache.prompt_hash == prompt_hash
            )
        )

        cache_row = cached_db.scalar_one_or_none()

        if cache_row:
            data = json.loads(cache_row.response)
            set_cache(cache_key, data)  # sync RAM
            print("🧠 DB CACHE HIT")
            return data

    # ----------------------
    # 3. GPT GENERATION
    # ----------------------
    for attempt in range(MAX_RETRIES):
        try:
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": get_system_prompt(target_code)},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.6,
                max_tokens=1500,
                response_format={"type": "json_object"},
            )
 
            content = response.choices[0].message.content
 
            # Защита от пустого ответа (была причина fallback через раз)
            if not content or not content.strip():
                raise ValueError("Empty response from model")
 
            data = json.loads(content)
 

            print("🔥 RAW GPT RESPONSE:")
            print(content)

            print("🔥 PARSED DATA:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            print("VOCAB ONLY:")
            print(data["vocab"])

            # ----------------------
            # VALIDATION
            # ----------------------
            required_fields = ["title", "text", "translation", "vocab", "questions"]

            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing field: {field}")

            # ----------------------
            # 4. SAVE CACHE (DB + RAM)
            # ----------------------
            async with AsyncSessionLocal() as session:
                session.add(AICache(
                    level=user.level,
                    prompt_hash=prompt_hash,
                    response=json.dumps(data)
                ))
                await session.commit()

            set_cache(cache_key, data)

            print("💾 SAVED TO CACHE")

            return data

        except Exception as e:
            print(f"AI attempt {attempt+1} failed:", e)
            await asyncio.sleep(BASE_DELAY * (attempt + 1))

    return get_fallback_lesson(target_code)


def get_fallback_lesson(target_code: str = "en") -> dict:
    """Fallback при сбое GPT; слова — на изучаемом языке (для en — старый шаблон)."""
    if (target_code or "en") == "en":
        return FALLBACK_LESSON

    target = language_name(target_code)
    return {
        "title": f"Daily {target} Lesson",
        "text": f"[Lesson generation failed. Please try again later.]",
        "translation": "",
        "questions": [],
        "vocab": [],
    }

# Добавь в конец app/services/ai.py
# (client, AsyncOpenAI и т.д. уже импортированы вверху файла)

import json as _json

# ── Grounding helpers (check_text; та же логика, что в scene recap) ──

def _fragment_in_line(fragment: str, line: str) -> bool:
    fragment = fragment.strip()
    if not fragment:
        return False
    return fragment in line


def _has_lowercase_i_pronoun(line: str) -> bool:
    return bool(re.search(r"(?<![A-Za-z])i(?![A-Za-z])", line))


def _mentions_capital_i(text: str) -> bool:
    text_lower = text.lower()
    if not re.search(r"['\"]?i['\"]?", text_lower):
        return False
    return any(
        word in text_lower
        for word in (
            "заглавн", "больш", "capital", "letter", "букв", "always", "всегда",
            "with a capital", "с большой",
        )
    )


def _split_rule_sentences(rule: str) -> list[str]:
    parts = re.split(r"(?<=[.!?…])\s+|\n+", rule.strip())
    return [p.strip() for p in parts if p.strip()]


def _clean_i_capital_mentions(
    text: str,
    original: str,
    target_code: str,
    *,
    wrong: str = "",
) -> str:
    """Убирает фразы про заглавную I, если они не относятся к этой ошибке."""
    if target_code != "en" or _allows_i_capital_note(original, wrong):
        return text.strip()
    kept = [s for s in _split_rule_sentences(text) if not _mentions_capital_i(s)]
    return " ".join(kept).strip()


def _allows_i_capital_note(original: str, wrong: str) -> bool:
    """Можно упоминать I/im в пояснении, если это реально в тексте."""
    if _has_lowercase_i_pronoun(original):
        return True
    if re.search(r"\bim\b", original, re.I):
        return True
    w = wrong.lower().strip()
    return w in ("i", "im") or w.startswith("im")


def _meaningfully_different(a: str, b: str) -> bool:
    return a.strip().lower() != b.strip().lower()


def _sanitize_check_result(original: str, data: dict, target_code: str) -> dict:
    """Отсекает нерелевантные правила про «I»; сохраняет настоящие ошибки."""
    code = target_code or "en"
    explanations: list[dict] = []
    seen_rules: set[str] = set()
    gpt_has_errors = bool(data.get("has_errors"))
    corrected = (data.get("corrected") or original).strip()

    for exp in data.get("explanations") or []:
        wrong = (exp.get("wrong") or "").strip()
        right = (exp.get("right") or "").strip()
        rule = _clean_i_capital_mentions(
            exp.get("rule") or "", original, code, wrong=wrong,
        )
        if not wrong or not _fragment_in_line(wrong, original):
            continue
        if code == "en" and wrong == "i" and not _allows_i_capital_note(original, wrong):
            continue
        if not rule:
            continue
        rule_key = rule.lower()
        if rule_key in seen_rules:
            continue
        seen_rules.add(rule_key)
        explanations.append({"wrong": wrong, "right": right, "rule": rule})

    tip = _clean_i_capital_mentions(
        (data.get("tip") or "").strip(), original, code,
    )
    if code == "en" and tip and _mentions_capital_i(tip) and not _allows_i_capital_note(original, ""):
        tip = ""

    has_errors = bool(explanations) or (
        gpt_has_errors and _meaningfully_different(corrected, original)
    )
    if not has_errors:
        corrected = original
        tip = ""
        praise = (data.get("praise") or "").strip()
    else:
        praise = (data.get("praise") or "").strip()

    return {
        "has_errors": has_errors,
        "corrected": corrected,
        "explanations": explanations[:5],
        "tip": tip,
        "praise": praise if not has_errors else (praise or ""),
    }


CHECK_EN_I_OVERRIDE = (
    "CAPITAL 'I' / PRONOUN RULES (English): "
    "Standalone lowercase 'i' as its own word (e.g. 'i think') — minor; fix silently in "
    "'corrected', optional tip only, not a separate explanation unless it is the only issue. "
    "Broken or wrong pronoun forms — REAL errors: 'im' instead of 'I', 'I'm like coffee' when "
    "the learner means 'I like coffee' (wrong structure/meaning). Flag these in 'explanations' "
    "with a wrong fragment copied from the text (e.g. wrong='im like coffee', right='I like coffee'). "
    "NEVER add a generic capital-I lecture to unrelated errors. Never mention capital 'I' in tip "
    "or rule unless standalone lowercase 'i' or 'im' is actually in the text."
)

CHECK_GROUNDING_RULES = (
    "STRICT GROUNDING RULES (must follow): "
    "1) Each explanation must refer to words that actually appear in the student's text. "
    "Every 'wrong' field must be an exact case-sensitive substring of the text (a phrase is OK). "
    "2) One error — one relevant rule in plain language. Do not attach unrelated rules. "
    "3) Never repeat the same rule across multiple explanations. "
    "4) If the text has real grammar or meaning errors, has_errors MUST be true — do NOT praise. "
    "5) Praise and warm 'tip' only when the text is genuinely correct (has_errors=false)."
)

CHECK_EN_EXAMPLES = (
    "EXAMPLES (follow this pattern): "
    "'im like coffee' → has_errors=true, corrected='I like coffee', "
    "explanations=[{wrong:'im like coffee', right:'I like coffee', rule: plain explanation in native language}]. "
    "'I'm like coffee' (meaning: I enjoy coffee) → has_errors=true, corrected='I like coffee', "
    "explain that 'I'm like' means 'I resemble', not 'I enjoy'. "
    "'Rissian' → spelling error, flag it. "
    "'I like coffee.' with no issues → has_errors=false, praise only."
)

CHECK_SYSTEM_PROMPT = f"""
You are a warm, encouraging English teacher checking a student's writing.

The student is a learner practicing English. Your goal is to help them communicate better. Be friendly, but DO catch real mistakes — grammar, wrong structure, wrong word choice, and spelling. Do not praise incorrect text.

WHAT COUNTS AS A REAL ERROR (flag in 'explanations', set has_errors=true):
- Wrong grammar or structure that changes or breaks the meaning (e.g. "im like coffee", "I'm like coffee" when they mean enjoying coffee).
- Missing or wrong words, wrong verb forms, subject-verb agreement, wrong articles/prepositions.
- Wrong word choice or meaning (e.g. "I'm like" vs "I like").
- Clear spelling mistakes in words (e.g. "Rissian" → "Russian").
- Broken pronoun forms: "im", "ive" without apostrophe when "I" / "I've" is meant.

WHAT IS NOT A REAL ERROR (do NOT flag alone):
- Missing period or casual punctuation in short messages.
- Standalone lowercase "i" as its own word ONLY — fix in 'corrected', optional tip; do not treat as the only error if bigger mistakes exist.
- Stylistic preferences when the sentence is already correct and clear.

{CHECK_EN_I_OVERRIDE}

{CHECK_GROUNDING_RULES}

{CHECK_EN_EXAMPLES}

THE GENTLE TIP ('tip' field):
- Optional ONE small side note — only when relevant and the text is otherwise correct or the note is separate from main errors.
- Do NOT use 'tip' for punctuation. If has_errors=true, tip is usually "".

DECISION RULE:
- has_errors=true when ANY real error from the first list is present. Provide corrected text and explanations.
- has_errors=false ONLY when the text is genuinely correct. Then give warm praise; tip optional.
- NEVER say the text is excellent if corrected would differ in grammar or meaning.

Return STRICT VALID JSON only. No markdown, no extra text. Schema:
{{
  "has_errors": true/false,
  "corrected": "the corrected version of the full text (or the original if there are no real errors)",
  "explanations": [
    {{ "wrong": "the incorrect fragment", "right": "the correct fragment", "rule": "short, simple explanation in the student's native language" }}
  ],
  "tip": "an optional gentle note in the student's native language, or empty string",
  "praise": "one short encouraging sentence in the student's native language (only when has_errors=false)"
}}

Rules:
- Explanations, tip, and praise MUST be written in the student's NATIVE LANGUAGE (given below).
- Keep rule explanations short and simple, no linguistic jargon — like a friend, not a textbook.
- List at most 5 of the most important real errors.
- 'corrected' must fix all real errors in the full text.

"""


def get_check_system_prompt(target_language: str) -> str:
    """Промпт проверки: текст на изучаемом языке, пояснения на родном."""
    code = target_language or "en"
    if code == "en":
        return CHECK_SYSTEM_PROMPT

    target = language_name(code)
    return f"""
You are a warm, encouraging {target} teacher checking a student's writing.

The student is learning {target}. Check text written in {target}. Your goal is to help them communicate better. Be friendly, but DO catch real mistakes — grammar, wrong structure, wrong word choice, and spelling. Do not praise incorrect text.

WHAT COUNTS AS A REAL ERROR (flag in 'explanations', set has_errors=true):
- Wrong grammar or structure that changes or breaks the meaning.
- Missing or wrong words, wrong verb forms, agreement, wrong articles/prepositions/cases.
- Wrong word choice or meaning.
- Clear spelling mistakes.

WHAT IS NOT A REAL ERROR (do NOT flag alone):
- Missing period or casual punctuation in short messages.
- Minor capitalization in otherwise correct casual text.
- Stylistic preferences when the sentence is already correct and clear.

THE GENTLE TIP ('tip' field):
- Optional ONE small side note — only when relevant and the text is otherwise correct.
- If has_errors=true, tip is usually "".

{CHECK_GROUNDING_RULES}

DECISION RULE:
- has_errors=true when ANY real error is present. Provide corrected text and explanations.
- has_errors=false ONLY when the text is genuinely correct. Then give warm praise.
- NEVER praise if corrected would differ in grammar or meaning.

Return STRICT VALID JSON only. No markdown, no extra text. Schema:
{{
  "has_errors": true/false,
  "corrected": "the corrected version of the full text (or the original if there are no real errors)",
  "explanations": [
    {{ "wrong": "the incorrect fragment", "right": "the correct fragment", "rule": "short, simple explanation in the student's native language" }}
  ],
  "tip": "an optional gentle note in the student's native language, or empty string",
  "praise": "one short encouraging sentence in the student's native language"
}}

Rules:
- The text being checked is in {target}.
- Explanations, tip, and praise MUST be written in the student's NATIVE LANGUAGE (given below), so a beginner understands.
- Keep rule explanations short and simple, no linguistic jargon — like a friend, not a textbook.
- List at most 5 of the most important real errors. If there are more, pick the ones that matter most for being understood.
- 'corrected' should fix the real errors but otherwise stay faithful to what the student wrote — keep their informal style.

"""


async def check_user_text(
    text: str,
    native_language: str,
    *,
    target_language: str = "en",
    context: str | None = None,
) -> dict:
    """Проверяет текст на изучаемом языке; пояснения — на native_language."""
    target_code = target_language or "en"
    target_lang = language_name(target_code)

    user_prompt = (
        f"Language being learned (text language): {target_lang}\n"
        f"Student's native language (for explanations, tip, praise): {native_language}\n\n"
    )
    if context:
        user_prompt += f"Additional context:\n{context}\n\n"
    user_prompt += f"Check this {target_lang} text:\n\n{text}"

    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": get_check_system_prompt(target_code)},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,  # для проверки нужна точность, не креатив
        )
        content = response.choices[0].message.content
        data = _json.loads(content)

        # минимальная валидация
        if "has_errors" not in data or "corrected" not in data:
            raise ValueError("bad structure")
        data.setdefault("explanations", [])
        data.setdefault("tip", "")
        data.setdefault("praise", "")
        return _sanitize_check_result(text, data, target_code)

    except Exception as e:
        print("check_user_text failed:", e)
        return {
            "has_errors": False,
            "corrected": text,
            "explanations": [],
            "tip": "",                   # <- и здесь, чтобы хендлер не упал
            "praise": "",
            "_error": True,  # флаг что проверка не удалась
        }


async def scene_chat(messages: list[dict[str, str]]) -> str | None:
    """Диалог в сценке: отправляет историю в gpt-4o, возвращает ответ бариста."""
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.7,
        )
        content = response.choices[0].message.content
        if not content or not content.strip():
            raise ValueError("Empty response from model")
        return content.strip()
    except Exception as e:
        print("scene_chat failed:", e)
        return None


async def text_to_speech(text: str) -> bytes | None:
    """
    Озвучивает текст через OpenAI TTS (POST /v1/audio/speech).
    Язык определяется содержимым text (урок уже на target_language).
    Вызывается только по нажатию «Прослушать», не при генерации урока.
    """
    try:
        response = await client.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice="alloy",
            input=text,
            response_format="mp3",
        )
        return response.content
    except Exception:
        logging.exception("TTS error")
        return None