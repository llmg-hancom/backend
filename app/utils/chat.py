from typing import Annotated

from fastapi import Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from db.session import get_async_db
from errors.chat import ChatSessionNotFoundError
from errors.space import SpaceNotFoundError
from models import ChatSession, ChatSpace


async def chat_space_from_space_id_path(
    space_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(get_async_db)]
) -> ChatSpace:
    query = (
        select(ChatSpace)
        .where(ChatSpace.space_id == space_id)
        .where(col(ChatSpace.deleted_at).is_(None))
    )

    result = await session.scalar(query)

    if result is None:
        raise SpaceNotFoundError(space_id=space_id)

    return result


async def chat_session_from_session_id_path(
    session_id: Annotated[int, Path(description="채팅 세션 ID")],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> ChatSession:
    query = (select(ChatSession).where(ChatSession.session_id == session_id))
    result = await db.scalar(query)

    if result is None:
        raise ChatSessionNotFoundError(session_id=session_id)

    # 삭제 시간이 존재하는 경우
    if result.deleted_at is not None:
        raise ChatSessionNotFoundError(session_id=session_id)

    return result
