from pydantic import PositiveInt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from models import Group, GroupMember, User


async def get_group_members(
    group: Group,
    db: AsyncSession,
    offset: PositiveInt,
    limit: PositiveInt,
) -> list[User]:
    query = (
        select(User)
        .join(GroupMember)
        .where(col(GroupMember.group_id) == group.group_id)
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    return list(result.scalars().all())
