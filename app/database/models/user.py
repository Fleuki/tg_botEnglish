from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Date
from datetime import datetime
from app.database.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True)
    interface_language = Column(String, default="en")
    native_language = Column(String)
    target_language = Column(String, default="en", server_default="en")
    level = Column(String)
    lesson_time = Column(String)
    last_activity_date = Column(DateTime, default=datetime.utcnow)
    streak_days = Column(Integer, default=0)

    preferred_topic = Column(String, default="general")

    # Счётчик уроков за день (защита от перерасхода API).
    lessons_today = Column(Integer, default=0)
    lessons_date = Column(Date, nullable=True)
    # Добавь в класс User (в app/database/models/user.py),
    # рядом с lessons_today / lessons_date:

    # Счётчик проверок текста за день (своя пара, отдельно от уроков).
    checks_today = Column(Integer, default=0)
    checks_date = Column(Date, nullable=True)

# (Date уже импортирован вверху, мы добавляли его для lessons_date)