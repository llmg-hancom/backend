from typing import Annotated

from fastapi import APIRouter, Depends, Query, Security
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_async_db
from models.user import User, UserRead
from schemas.groups import GroupReadWithoutMembers
from schemas.pagination import PaginationParams, PaginationResponse
from services.users.get_my_group import get_my_group as service
from utils.auth import get_current_user


router = APIRouter()

@router.get(
    path="/groups",
    summary="현재 사용자가 소속된 그룹 조회",
    tags=["그룹"]
)
async def my_groups(
    user: Annotated[User, Security(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
    pagination: Annotated[PaginationParams, Query()]
) -> PaginationResponse[GroupReadWithoutMembers]:
    offset = (pagination.page - 1) * pagination.size
    limit = pagination.size

    response = await service(
        actor=user,
        db=db,
        offset=offset,
        limit=limit
    )

    return PaginationResponse(
        page=pagination.page,
        size=pagination.size,
        data=[GroupReadWithoutMembers.model_validate(group) for group in response]
    )
