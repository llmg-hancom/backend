from pydantic import PositiveInt
from sqlalchemy.orm import joinedload
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from models import Group, GroupMember
from schemas.groups import GroupMemberRead


async def get_group_members(
    group: Group,
    db: AsyncSession,
    offset: PositiveInt,
    limit: PositiveInt,
) -> list[GroupMemberRead]:
    query = (
        select(GroupMember)
        .where(col(GroupMember.group_id) == group.group_id)
        .offset(offset)
        .limit(limit)
        .options(joinedload(GroupMember.user))
    )
    result = await db.exec(query)
    return result.all()
