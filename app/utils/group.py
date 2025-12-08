from typing import Annotated

from fastapi import Depends, Path
from sqlalchemy import exists
from sqlalchemy.orm import joinedload
from sqlmodel import select, col
from sqlmodel.ext.asyncio.session import AsyncSession

from db.session import get_async_db
from errors.general import IllegalStateError
from errors.groups import (
    GroupNotExistError,
    UserIsNotGroupAdminError,
    UserIsNotGroupMemberError,
)
from models import GroupMember
from models.group import Group
from models.group_member import UserRole
from models.user import User
from utils.auth import get_current_user


async def get_group_from_group_id_path(
    group_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(get_async_db)],
) -> Group:
    """
    Path의 group_id를 이용해 Group를 조회하는 함수
    """
    group = (
        await session.exec(
            select(Group)
            .where(Group.group_id == group_id)
            .where(col(Group.deleted_at).is_(None))
            .options(joinedload(Group.created_by_user))  # type: ignore
        )
    ).one_or_none()

    if group is None:
        raise GroupNotExistError()
    return group


async def require_group_member(
    user: Annotated[User, Depends(get_current_user)],
    group: Annotated[Group, Depends(get_group_from_group_id_path)],
    session: Annotated[AsyncSession, Depends(get_async_db)],
) -> Group:
    """
    유저가 그룹 멤버인지 확인한 후, Group을 반환하는 함수
    """
    # 타입 체크용
    if user.user_id is None:
        raise IllegalStateError()

    statement = select(
        exists(GroupMember)
        .where(col(GroupMember.user_id) == user.user_id)
        .where(col(GroupMember.group_id) == group.group_id)
    )

    is_member = (await session.exec(statement)).one()

    if not is_member:
        raise UserIsNotGroupMemberError()

    return group


async def require_group_admin(
    user: Annotated[User, Depends(get_current_user)],
    group: Annotated[Group, Depends(get_group_from_group_id_path)],
    session: Annotated[AsyncSession, Depends(get_async_db)],
) -> Group:
    """
    유저가 그룹 admin인지 확인한 후, Group을 반환하는 함수
    """
    # 타입 체크용
    if user.user_id is None:
        raise IllegalStateError()

    statement = select(
        exists(GroupMember)
        .where(col(GroupMember.user_id) == user.user_id)
        .where(col(GroupMember.group_id) == group.group_id)
        .where(col(GroupMember.role) == UserRole.admin)
    )

    is_admin = (await session.exec(statement)).one()

    if not is_admin:
        raise UserIsNotGroupAdminError()

    return group
