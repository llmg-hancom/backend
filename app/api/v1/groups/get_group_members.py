from typing import Annotated

from fastapi import APIRouter, Depends, Query, Security
from sqlmodel.ext.asyncio.session import AsyncSession

from db.session import get_async_db
from models import Group
from schemas.groups import GroupMemberRead
from schemas.pagination import PaginationParams, PaginationResponse
from services.group.get_group_members import get_group_members as service
from utils.group import require_group_member

router = APIRouter()


@router.get("/{group_id}/members", summary="그룹 멤버 조회")
async def get_group_members(
    group: Annotated[Group, Security(require_group_member)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
    pagination: Annotated[PaginationParams, Query()],
) -> PaginationResponse[GroupMemberRead]:
    offset = (pagination.page - 1) * pagination.size
    limit = pagination.size

    result = await service(group=group, db=db, offset=offset, limit=limit)

    return PaginationResponse(page=pagination.page, size=pagination.size, data=result)
