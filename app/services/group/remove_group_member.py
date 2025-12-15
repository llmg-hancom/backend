from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from errors.groups import GroupMemberNotFound
from models.group import Group
from models.group_member import GroupMember


async def remove_group_member(
    group: Group, deleted_member_id: int, session: AsyncSession
):
    group_rel = (
        await session.exec(
            select(GroupMember)
            .where(GroupMember.user_id == deleted_member_id)
            .where(GroupMember.group_id == group.group_id)
        )
    ).one_or_none()

    # 그룹 멤버 관계가 존재하는지 확인
    if group_rel is None:
        raise GroupMemberNotFound()

    # 관계가 있으면 삭제
    await session.delete(group_rel)