from datetime import datetime, timezone
from typing import Annotated, Self

from fastapi import Depends, Security
from sqlmodel.ext.asyncio.session import AsyncSession

from db.session import get_async_db
from errors.chat import ForbiddenChatSessionAccessError
from errors.general import IllegalStateError
from models import ChatSession, User
from utils.auth import get_current_user


class ChatSessionService:
    db: AsyncSession
    actor: User

    def __init__(self, db: AsyncSession, actor: User):
        if actor.user_id is None:
            raise IllegalStateError()

        self.db = db
        self.actor = actor

    @classmethod
    def factory(
        cls,
        db: Annotated[AsyncSession, Depends(get_async_db)],
        actor: Annotated[User, Security(get_current_user)],
    ) -> Self:
        return cls(db, actor)

    async def delete_chat_session(self, session: ChatSession) -> None:
        """
        유저가 세션을 생성한 유저인지 확인하고, 세션을 삭제함
        """
        if self.actor.user_id is None:
            raise IllegalStateError()

        # actor와 session의 소유자가 다른 경우
        if session.user_id != self.actor.user_id:
            raise ForbiddenChatSessionAccessError()

        session.deleted_at = datetime.now(tz=timezone.utc)
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)

        return None
