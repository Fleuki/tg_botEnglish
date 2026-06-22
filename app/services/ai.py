import os
import json
import asyncio
from app.services.topics import pick_topic
from openai import AsyncOpenAI
from sqlalchemy import select
from app.database.db import AsyncSessionLocal
from app.database.models.ai_cache import AICache
from app.services.cache import make_prompt_hash
client = AsyncOpenAI(api_key=os.getenv("AI_TUNNEL_API_KEY"),
    base_url="https://api.aitunnel.ru/v1")
from app.database.models.user import User
from app.services.prompts import SYSTEM_PROMPT
from app.services.cache import make_prompt_hash, get_cache, set_cache
# -------------------------
# FALLBACK (обязательно)
# -------------------------
FALLBACK_LESSON = {
    "title": "Daily English",

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
        "vocab": "intermediate natural English",
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
English level: {user.level}

User native language:
{user.native_language}

Topic:
{topic}

Create:

1. A title.
2. A text of 7-10 sentences in English.
3. Full translation into {user.native_language}.
4. EXACTLY 3 comprehension questions.
5. 4-5 vocabulary words from the text.
6. Vocabulary translations must be in {user.native_language}.
7. Do NOT use any other language for translations.
Return JSON only.

IMPORTANT:
Vocabulary translations must be in the same language as the full translation.

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
                    {"role": "system", "content": SYSTEM_PROMPT},
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

    return FALLBACK_LESSON

# Добавь в конец app/services/ai.py
# (client, AsyncOpenAI и т.д. уже импортированы вверху файла)

import json as _json

CHECK_SYSTEM_PROMPT = """
You are a warm, encouraging English teacher checking a student's writing.

The student is a learner practicing English. Your goal is to help them communicate better — NOT to enforce perfect formatting. Over-correction discourages learners, so flag only mistakes that actually affect understanding or are clearly wrong grammar.

WHAT COUNTS AS A REAL ERROR (flag these in 'explanations'):
- Grammar that affects meaning: verb tense, subject-verb agreement, plurals.
- Wrong or missing articles where it clearly sounds wrong (a / an / the).
- Wrong prepositions (e.g. "depend of" -> "depend on").
- Wrong word choice, or a word that doesn't fit the meaning.
- Word order that sounds unnatural or wrong.
- Real spelling mistakes (not just informal style).

WHAT IS NOT A REAL ERROR (do NOT put these in 'explanations', do NOT set has_errors for them, do NOT change them in 'corrected'):
- A missing period or other end punctuation, especially in short or informal messages.
- Lowercase "i" instead of "I", or a missing capital letter at the start, in casual short text.
- Stylistic preferences when the sentence is already correct and clear.
- Anything a native speaker would understand perfectly and not bother correcting in a friendly chat.
- IMPORTANT: lowercase "i" and missing punctuation must NEVER appear in 'explanations', even when the text has other real errors. If you find a real error AND the text has a lowercase "i", correct the "i" silently inside 'corrected', keep it OUT of 'explanations', and you may mention it only in 'tip'.

THE GENTLE TIP ('tip' field):
- This is separate from errors. Use it for ONE small, friendly note about capitalization of the word "I" — that in English "I" is always written as a capital letter. Do NOT use 'tip' for punctuation (periods, commas) — never mention missing periods at all.
- Phrase it kindly and casually, like a side remark, not a correction. It must NOT sound like the student made a mistake.
- Use 'tip' for at most ONE such note, and only when it's actually relevant. If there's nothing minor worth mentioning, set "tip" to "".
- 'tip' NEVER affects has_errors and NEVER appears in 'explanations'.DECISION RULE:
- has_errors=true ONLY when there is at least one REAL error from the first list.
- If the only issues are minor formatting things, set has_errors=false, corrected=original, explanations=[], give warm praise, and optionally add a gentle 'tip'.

Return STRICT VALID JSON only. No markdown, no extra text. Schema:
{
  "has_errors": true/false,
  "corrected": "the corrected version of the full text (or the original if there are no real errors)",
  "explanations": [
    { "wrong": "the incorrect fragment", "right": "the correct fragment", "rule": "short, simple explanation of the rule in the student's native language" }
  ],
  "tip": "an optional gentle note in the student's native language, or empty string",
  "praise": "one short encouraging sentence in the student's native language"
}

Rules:
- Explanations, tip, and praise MUST be written in the student's NATIVE LANGUAGE (given below), so a beginner understands.
- Keep rule explanations short and simple, no linguistic jargon.
- List at most 5 of the most important real errors. If there are more, pick the ones that matter most for being understood.
- 'corrected' should fix the real errors but otherwise stay faithful to what the student wrote — keep their informal style.

"""


async def check_user_text(text: str, native_language: str) -> dict:
    """Проверяет текст пользователя на ошибки. Возвращает разбор в виде dict."""
    user_prompt = (
        f"Student's native language: {native_language}\n\n"
        f"Check this English text:\n\n{text}"
    )

    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": CHECK_SYSTEM_PROMPT},
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
        data.setdefault("tip", "")       # <- новое поле, мягкая подсказка
        data.setdefault("praise", "")
        return data

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