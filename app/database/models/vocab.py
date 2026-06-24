# app/database/models/vocab.py

from sqlalchemy import Column, Integer, String, DateTime, BigInteger
from app.database.db import Base
from datetime import datetime

class Vocab(Base):
    __tablename__ = "vocab"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, index=True)

    word = Column(String)
    translation = Column(String)
    target_language = Column(String, default="en", server_default="en")

    stage = Column(Integer, default=0)
    next_review = Column(DateTime, default=datetime.utcnow)