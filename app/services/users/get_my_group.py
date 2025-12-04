from sqlalchemy.orm import joinedload
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from errors.general import IllegalStateError
from models import Group, GroupMember, User
from schemas.groups import GroupReadWithMyRole


async def get_my_group(
    actor: User, db: AsyncSession, offset: int, limit: int
) -> list[GroupReadWithMyRole]:
    if actor.user_id is None:
        raise IllegalStateError()

    query = (
        select(Group, GroupMember)
        .join(GroupMember)
        .where(col(GroupMember.user_id) == actor.user_id)
        .where(col(Group.deleted_at).is_(None))
        .offset(offset)
        .limit(limit)
        .options(joinedload(Group.created_by_user)) # type:ignore
    )

    result = await db.exec(query)
    response = [
        GroupReadWithMyRole(
            group_name=group.group_name,
            description=group.description,
            group_id=group.group_id,
            created_at=group.created_at,
            created_by_user=group.created_by_user,
            user_role=membership.role,
        )
        for group, membership in result.all()
    ]
    return response
