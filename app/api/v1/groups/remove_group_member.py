from typing import Annotated

from fastapi import APIRouter, Depends, Path, Security, status
from sqlmodel.ext.asyncio.session import AsyncSession

from db.session import get_async_db
from models.group import Group
from services.group.remove_group_member import (
    remove_group_member as remove_group_member_service,
)
from utils.group import require_group_admin


router = APIRouter()


@router.delete(
    path="/{group_id}/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="그룹에서 유저 탈퇴",
)
async def remove_group_member(
    group: Annotated[Group, Security(require_group_admin)],
    member_id: Annotated[int, Path()],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> None:
    await remove_group_member_service(
        group=group, deleted_member_id=member_id, session=db
    )
