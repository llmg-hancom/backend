from pydantic import PositiveInt
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

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
    result = await db.exec(query)
    return list(result.all())
