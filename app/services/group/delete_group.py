from datetime import datetime, timezone

from sqlmodel import col, exists, select
from sqlmodel.ext.asyncio.session import AsyncSession

from errors.general import IllegalStateError
from errors.groups import UserIsNotGroupAdminError
from models import Group, GroupMember, User


async def delete_group(actor: User, group: Group, db: AsyncSession) -> None:
    if actor.user_id is None:
        raise IllegalStateError()

    # actor가 그룹의 admin인지 확인
    admin_query = select(
        exists(GroupMember)
        .where(col(GroupMember.user_id) == actor.user_id)
        .where(col(GroupMember.group_id) == group.group_id)
        .where(col(GroupMember.role) == "admin")
    )

    admin_exists = await db.scalar(admin_query)
    if not admin_exists:
        raise UserIsNotGroupAdminError()

    group.deleted_at = datetime.now(tz=timezone.utc)

    db.add(group)

    return None
