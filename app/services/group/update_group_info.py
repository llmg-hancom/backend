from typing import Annotated

from fastapi import Depends, Security
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import col, exists, select

from db.session import get_async_db
from errors.general import IllegalStateError
from errors.groups import UserIsNotGroupAdminError
from models import Group, GroupMember, User
from models.group_member import UserRole
from utils.auth import get_current_user
from utils.group import get_group_from_group_id_path


async def update_group_info(
    actor: Annotated[User, Security(get_current_user)],
    group: Annotated[Group, Depends(get_group_from_group_id_path)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
    name: str | None = None,
    description: str | None = None,
) -> Group:
    if actor.user_id is None:
        raise IllegalStateError()

    # actor가 그룹의 admin인지 검사
    admin_query = select(
        exists(GroupMember)
        .where(col(GroupMember.user_id) == actor.user_id)
        .where(col(GroupMember.group_id) == group.group_id)
        .where(col(GroupMember.role) == UserRole.admin)
    )

    admin_exists = await db.scalar(admin_query)
    if not admin_exists:
        raise UserIsNotGroupAdminError()

    group.group_name = name or group.group_name
    group.description = description

    db.add(group)
    await db.flush()
    await db.refresh(group, attribute_names=["created_by_user"])

    return group
