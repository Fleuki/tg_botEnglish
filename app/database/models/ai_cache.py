from sqlalchemy import Column, Integer, String, Text, DateTime, UniqueConstraint
from datetime import datetime

from app.database.db import Base


class AICache(Base):
    __tablename__ = "ai_cache"

    id = Column(Integer, primary_key=True)

    level = Column(String, index=True)
    prompt_hash = Column(String, index=True)

    response = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("level", "prompt_hash", name="uq_level_prompt"),
    )