from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlmodel import col, select

from errors.general import IllegalStateError
from models import Group, GroupMember, User


async def get_my_group(actor: User, db: AsyncSession, offset: int, limit: int) -> list[Group]:
    if actor.user_id is None:
        raise IllegalStateError()

    query = (
        select(Group)
        .join(GroupMember)
        .where(col(GroupMember.user_id) == actor.user_id)
        .where(col(Group.deleted_at).is_(None))
        .offset(offset)
        .limit(limit)
        .options(joinedload(Group.created_by_user))
    )

    result = await db.execute(query)
    return list(result.scalars().all())
