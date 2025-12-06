from typing import Annotated

from fastapi import APIRouter, Depends, Query, Security
from sqlmodel.ext.asyncio.session import AsyncSession

from db.session import get_async_db
from errors.general import IllegalStateError
from models import User
from schemas.chat import SpaceRead
from schemas.pagination import PaginationParams, PaginationResponse
from services.users.get_user_space import get_user_space as service
from utils.auth import get_current_user


router = APIRouter()

@router.get("/spaces", summary="사용자의 스페이스 조회")
async def get_users_space(
    pagination: Annotated[PaginationParams, Query()],
    user: Annotated[User, Security(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_async_db)]
) -> PaginationResponse[SpaceRead]:
    if user.user_id is None:
        raise IllegalStateError()

    offset = (pagination.page - 1) * pagination.size
    limit = pagination.size

    data = await service(
        user=user,
        session=session,
        offset=offset,
        limit=limit
    )

    return PaginationResponse(
        page=pagination.page,
        size=pagination.size,
        data=[
            SpaceRead.model_validate(d)
            for d in data
        ],
    )
