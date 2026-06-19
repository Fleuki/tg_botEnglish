import asyncio
from app.database.db import engine, Base
from app.database.models.user import User
from app.database.models.vocab import Vocab

async def init_models():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    asyncio.run(init_models())