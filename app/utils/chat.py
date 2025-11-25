from typing import Annotated

from fastapi import Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from db.session import get_async_db
from errors.space import SpaceNotFoundError
from models import ChatSpace


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
