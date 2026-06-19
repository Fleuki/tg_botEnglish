import random

TOPICS = {
    "A1": [
        "family",
        "food",
        "shopping",
        "pets",
        "weather",
        "daily routine",
        "hobbies"
    ],

    "A2": [
        "travel",
        "school",
        "technology",
        "work",
        "health"
    ],

    "B1": [
        "business",
        "communication",
        "friendship",
        "sports",
        "culture"
    ],

    "B2": [
        "history",
        "economics",
        "psychology",
        "society",
        "environment"
    ],

    "C1": [
        "artificial intelligence",
        "neuroscience",
        "astronomy",
        "genetics",
        "climate change",
        "philosophy",
        "linguistics"
    ]
}

TEXT_TYPES = {
    "A1": ["story", "dialogue"],
    "A2": ["story", "dialogue", "email"],
    "B1": ["story", "news article", "interview"],
    "B2": ["article", "blog post", "interview"],
    "C1": [
        "scientific article",
        "popular science article",
        "magazine article"
    ]
}

USED_TOPICS = set()


def pick_topic(user):
    level_topics = TOPICS.get(user.level, TOPICS["A2"])

    available = [t for t in level_topics if t not in USED_TOPICS]

    if not available:
        USED_TOPICS.clear()
        available = level_topics

    topic = random.choice(available)
    USED_TOPICS.add(topic)

    return topic


def pick_text_type(user):
    return random.choice(
        TEXT_TYPES.get(user.level, ["story"])
    )

