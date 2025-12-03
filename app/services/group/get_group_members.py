from pydantic import PositiveInt
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from models import Group, GroupMember, User
from schemas.groups import GroupMemberRead


async def get_group_members(
    group: Group,
    db: AsyncSession,
    offset: PositiveInt,
    limit: PositiveInt,
) -> list[GroupMemberRead]:
    query = (
        select(User, GroupMember.role)
        .join(GroupMember)
        .where(col(GroupMember.group_id) == group.group_id)
        .offset(offset)
        .limit(limit)
    )
    result = await db.exec(query)
    members = [GroupMemberRead.model_validate(user) for user in result.all()]
    return members
