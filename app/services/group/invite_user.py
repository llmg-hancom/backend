from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from errors.general import IllegalStateError
from errors.groups import (
    InviteeIsAlreadyInGroupError,
    InviteeIsNotExistError,
)
from models.group import Group
from models.group_member import GroupMember
from models.user import User
from schemas.groups import GroupUserInviteRequest


async def invite_user(
    inviter: User,
    session: AsyncSession,
    group: Group,
    body: GroupUserInviteRequest,
) -> None:
    # 타입 체크용
    if inviter.user_id is None:
        raise IllegalStateError()

    # 초대받은 사용자 검색
    invitee = (
        await session.exec(
            select(User)
            .where(User.email == body.email)
            .options(selectinload(User.group_memberships))  # type:ignore
        )
    ).one_or_none()

    # 초대받은 유저가 데이터베이스에 없을 경우
    if invitee is None:
        raise InviteeIsNotExistError()

    # 초대받은 유저가 이미 그룹에 속해있을 경우
    if group.group_id in [
        membership.group_id for membership in invitee.group_memberships
    ]:
        raise InviteeIsAlreadyInGroupError()

    user_group_rel = GroupMember(
        user_id=invitee.user_id, group_id=group.group_id, role=body.role
    )
    session.add(user_group_rel)
