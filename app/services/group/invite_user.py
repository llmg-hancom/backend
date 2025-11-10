from sqlmodel import Session, select

from errors.groups import InviteeIsAlreadyInGroupError, InviteeIsNotExistError
from models.group_member import GroupMember
from models.user import User
from schemas.groups import GroupUserInviteRequest


def invite_user(
    inviter: User,
    session: Session,
    group_id: int,
    body: GroupUserInviteRequest,
) -> None:
    # 타입 체크용
    if inviter.user_id is None:
        raise RuntimeError("데이터베이스에서 불러온 User의 user_id가 None임")

    # 초대받은 사용자 검색
    invitee = session.exec(select(User).where(User.email == body.email)).one_or_none()

    # 초대받은 유저가 데이터베이스에 없을 경우
    if invitee is None:
        raise InviteeIsNotExistError()

    # 초대받은 유저가 이미 그룹에 속해있을 경우
    if group_id in [group.group_id for group in invitee.group_memberships]:
        raise InviteeIsAlreadyInGroupError()

    # 타입 체크용
    if invitee.user_id is None:
        raise RuntimeError("데이터베이스에서 불러온 User의 user_id가 None임")

    user_group_rel = GroupMember(user_id=invitee.user_id, group_id=group_id)
    session.add(user_group_rel)
    session.commit()
