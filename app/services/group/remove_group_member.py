from sqlmodel import Session, select

from errors.groups import GroupMemberNotFound
from models.group import Group
from models.group_member import GroupMember


def remove_group_member(
    group: Group,
    deleted_member_id: int,
    session: Session
):
    group_rel = session.exec(
        select(GroupMember)
        .where(GroupMember.group_id == group.group_id)
        .where(GroupMember.user_id == deleted_member_id)
    ).one_or_none()

    # 그룹 멤버 관계가 존재하는지 확인
    if group_rel is None:
        raise GroupMemberNotFound()

    # 관계가 있으면 삭제
    session.delete(group_rel)
    session.commit()
