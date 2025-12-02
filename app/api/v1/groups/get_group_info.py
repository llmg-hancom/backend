from typing import Annotated

from fastapi import APIRouter, Depends, Security
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_async_db
from models import Group, User
from schemas.groups import GroupReadWithoutMembers
from services.group.get_group_info import get_group_info as service
from utils.auth import get_current_user
from utils.group import get_group_from_group_id_path


router = APIRouter()

@router.get(
    "/{group_id}",
    summary="그룹 상세정보 조회"
)
async def get_group_info(
    group: Annotated[Group, Depends(get_group_from_group_id_path)],
    actor: Annotated[User, Security(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_db)]
) -> GroupReadWithoutMembers:
    result = await service(group=group, db=db)
    return GroupReadWithoutMembers.model_validate(result)
