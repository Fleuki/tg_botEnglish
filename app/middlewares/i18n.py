from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, Update
from typing import Callable, Dict, Any, Awaitable

from sqlalchemy import select

from app.database.db import AsyncSessionLocal
from app.database.models.user import User


class I18nMiddleware(BaseMiddleware):

    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ):

        user_id = None

        if isinstance(event, Message):
            user_id = event.from_user.id

        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id

        elif isinstance(event, Update):
            if event.message:
                user_id = event.message.from_user.id
            elif event.callback_query:
                user_id = event.callback_query.from_user.id

        lang = "en"
        user = None

        if user_id:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(User).where(User.telegram_id == user_id)
                )
                user = result.scalar_one_or_none()

            if user and user.interface_language:
                lang = user.interface_language

        data["user"] = user
        data["lang"] = lang

        return await handler(event, data)