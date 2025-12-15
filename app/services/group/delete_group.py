from datetime import datetime, timezone

from sqlalchemy import delete, update
from sqlmodel import col, exists, select
from sqlmodel.ext.asyncio.session import AsyncSession

from errors.general import IllegalStateError
from errors.groups import UserIsNotGroupAdminError
from models import ChatSpace, Group, GroupMember, User
from models.group_member import UserRole


async def delete_group(actor: User, group: Group, db: AsyncSession) -> None:
    if actor.user_id is None:
        raise IllegalStateError()

    # 1. actor가 그룹의 admin인지 확인
    admin_query = select(
        exists(GroupMember).where(
            col(GroupMember.user_id) == actor.user_id,
            col(GroupMember.group_id) == group.group_id,
            col(GroupMember.role) == UserRole.admin,
        )
    )
    admin_exists = (await db.exec(admin_query)).one()
    if not admin_exists:
        raise UserIsNotGroupAdminError()

    # 2. GroupMember 레코드들을 한 번에 삭제 (Hard delete)
    await db.exec(
        delete(GroupMember).where(col(GroupMember.group_id) == group.group_id)
    )

    # 3. ChatSpace 레코드들을 한 번에 soft delete 처리
    await db.exec(
        update(ChatSpace)
        .where(col(ChatSpace.group_id) == group.group_id)
        .values(deleted_at=datetime.now(tz=timezone.utc))
    )

    # 4. Group 자체를 soft delete 처리
    group.deleted_at = datetime.now(tz=timezone.utc)
    db.add(group)

    # 세션이 커밋될 때 위의 모든 변경사항이 트랜잭션으로 처리됩니다.
    return None
