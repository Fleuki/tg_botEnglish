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
                temperature=0.85,
            )

            content = response.choices[0].message.content
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
You are a friendly, encouraging English teacher checking a student's writing.

The student writes text in English. You analyze it for mistakes (grammar, word choice, articles, prepositions, word order, spelling).

Return STRICT VALID JSON only. No markdown, no extra text. Schema:
{
  "has_errors": true/false,
  "corrected": "the corrected version of the full text (or the original if perfect)",
  "explanations": [
    { "wrong": "the incorrect fragment", "right": "the correct fragment", "rule": "short, simple explanation of the rule in the student's native language" }
  ],
  "praise": "one short encouraging sentence in the student's native language"
}

Rules:
- Explanations and praise MUST be written in the student's NATIVE LANGUAGE (given below), so a beginner understands.
- Keep rule explanations short and simple, no linguistic jargon.
- If the text is correct, set has_errors=false, corrected=original, explanations=[], and give warm praise.
- If there are errors, list each meaningful one (max 5) in explanations.
- Optionally, if the text is correct but could sound more natural, you may still suggest a smoother version in 'corrected' and note it gently in praise.
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
        data.setdefault("praise", "")
        return data

    except Exception as e:
        print("check_user_text failed:", e)
        return {
            "has_errors": False,
            "corrected": text,
            "explanations": [],
            "praise": "",
            "_error": True,  # флаг что проверка не удалась
        }