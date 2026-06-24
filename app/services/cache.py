import hashlib
CACHE = {}

def get_cache(key: str):
    return CACHE.get(key)


def set_cache(key: str, value):
    CACHE[key] = value

def make_prompt_hash(user, topic: str) -> str:
    raw = f"{user.level}:{user.target_language or 'en'}:{user.interface_language}:{user.native_language}:{topic}"
    return hashlib.sha256(raw.encode()).hexdigest()
