from typing import Annotated

from fastapi import APIRouter, Depends, Security, status
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_async_db
from errors.groups import UserIsNotGroupAdminError
from models import Group, User
from services.group.delete_group import delete_group as service
from utils.auth import get_current_user
from utils.group import get_group_from_group_id_path
from utils.openapi import generate_openapi_error_response as error_docs


router = APIRouter()

@router.delete(
    "/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    responses={
        **error_docs(
            UserIsNotGroupAdminError()
        )
    }
)
async def delete_group(
    actor: Annotated[User, Security(get_current_user)],
    group: Annotated[Group, Depends(get_group_from_group_id_path)],
    db: Annotated[AsyncSession, Depends(get_async_db)]
) -> None:
    return await service(
        actor=actor,
        group=group,
        db=db
    )
