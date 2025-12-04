from typing import Annotated

from fastapi import APIRouter, Depends, Query, Security
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_async_db
from models import Group
from models.user import UserRead
from schemas.groups import GroupMemberRead
from schemas.pagination import PaginationParams, PaginationResponse
from services.group.get_group_members import get_group_members as service
from utils.auth import get_current_user
from utils.group import get_group_from_group_id_path


router = APIRouter()


@router.get("/{group_id}/members", summary="그룹 멤버 조회")
async def get_group_members(
    group: Annotated[Group, Depends(get_group_from_group_id_path)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
    pagination: Annotated[PaginationParams, Query()],
    actor: Annotated[UserRead, Security(get_current_user)],
) -> PaginationResponse[GroupMemberRead]:
    offset = (pagination.page - 1) * pagination.size
    limit = pagination.size

    result = await service(group=group, db=db, offset=offset, limit=limit)

    return PaginationResponse(page=pagination.page, size=pagination.size, data=result)
