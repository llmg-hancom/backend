from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from errors.general import IllegalStateError
from models import ChatSpace
from models.user import User


async def get_user_space(
    user: User, session: AsyncSession, offset: int, limit: int
) -> list[ChatSpace]:
    if user.user_id is None:
        raise IllegalStateError()

    query = (
        select(ChatSpace)
        .where(ChatSpace.owner_user_id == user.user_id)
        .offset(offset)
        .limit(limit)
    )

    data = (await session.exec(query)).all()

    return list(data)
