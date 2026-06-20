from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import DATABASE_URL

echo = DATABASE_URL.startswith("sqlite")

engine = create_async_engine(DATABASE_URL, echo=echo)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db():
    from app.database.models.user import User
    from app.database.models.vocab import Vocab
    from app.database.models.ai_cache import AICache

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)