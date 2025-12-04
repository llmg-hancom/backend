from typing import Annotated

from fastapi import APIRouter, Body, Depends, Security
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_async_db
from errors.groups import UserIsNotGroupAdminError
from models import Group, User
from schemas.groups import GroupReadWithoutMembers, GroupUpdate
from services.group.update_group_info import update_group_info as service
from utils.auth import get_current_user
from utils.group import get_group_from_group_id_path
from utils.openapi import generate_openapi_error_response as error_docs


router = APIRouter()


@router.patch(
    "/{group_id}",
    summary="그룹 정보 변경",
    responses={**error_docs(UserIsNotGroupAdminError())},
)
async def update_group_info(
    actor: Annotated[User, Security(get_current_user)],
    group: Annotated[Group, Depends(get_group_from_group_id_path)],
    body: Annotated[GroupUpdate, Body()],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> GroupReadWithoutMembers:
    change_group = await service(
        actor=actor,
        group=group,
        name=body.group_name,
        description=body.description,
        db=db,
    )

    return change_group
