from typing import Annotated

from fastapi import Depends, Path
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from db.session import get_async_db
from errors.chat import ChatSessionNotFoundError
from errors.space import SpaceNotFoundError
from models import ChatSession, ChatSpace


async def chat_space_from_space_id_path(
    space_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(get_async_db)],
) -> ChatSpace:
    query = (
        select(ChatSpace)
        .where(ChatSpace.space_id == space_id)
        .where(col(ChatSpace.deleted_at).is_(None))
    )

    result = (await session.exec(query)).one_or_none()

    if result is None:
        raise SpaceNotFoundError(space_id=space_id)

    return result


async def chat_session_from_session_id_path(
    session_id: Annotated[int, Path(description="채팅 세션 ID")],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> ChatSession:
    query = (
        select(ChatSession)
        .where(ChatSession.session_id == session_id)
        .where(col(ChatSession.deleted_at).is_(None))
    )
    result = (await db.exec(query)).one_or_none()

    if result is None:
        raise ChatSessionNotFoundError(session_id=session_id)

    return result
