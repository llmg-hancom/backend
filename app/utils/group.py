from typing import Annotated

from fastapi import Depends, Path
from sqlmodel import Session, select

from db.session import get_db
from errors.general import IllegalStateError
from errors.groups import (
    GroupNotExistError,
    UserIsNotGroupAdminError,
    UserIsNotGroupMemberError,
)
from models.group import Group
from models.user import User
from utils.auth import get_current_user


def get_group_from_group_id_path(
    group_id: Annotated[int, Path()],
    session: Annotated[Session, Depends(get_db)]
) -> Group:
    group = session.exec(select(Group).where(Group.group_id == group_id)).one_or_none()

    if group is None:
        raise GroupNotExistError()

    return group


def require_group_member(
    user: Annotated[User, Depends(get_current_user)],
    group: Annotated[Group, Depends(get_group_from_group_id_path)]
) -> Group:
    # 타입 체크용
    if user.user_id is None:
        raise IllegalStateError()

    member_ids = [g.user_id for g in group.members]

    if user.user_id not in member_ids:
        raise UserIsNotGroupMemberError()

    return group


def require_group_admin(
    user: Annotated[User, Depends(get_current_user)],
    group: Annotated[Group, Depends(get_group_from_group_id_path)]
) -> Group:
    # 타입 체크용
    if user.user_id is None:
        raise IllegalStateError()

    admin_ids = [g.user_id for g in group.members if g.role == "admin"]

    if user.user_id not in admin_ids:
        raise UserIsNotGroupAdminError()

    return group
