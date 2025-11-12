from typing import Annotated

from fastapi import APIRouter, Body, Depends, status, Security
from sqlmodel import Session

from db.session import get_db
from models.user import User, UserEdit, UserRead
from utils.auth import get_current_user


router = APIRouter()


@router.patch(path="/", status_code=status.HTTP_200_OK, summary="유저 정보 변경")
def edit_user_info(
    user: Annotated[User, Security(get_current_user)],
    user_edit: Annotated[UserEdit, Body()],
    session: Annotated[Session, Depends(get_db)],
) -> UserRead:
    """
    사용자의 정보를 변경합니다.
    """

    user_edit_data = user_edit.model_dump(exclude_unset=True)
    user = user.sqlmodel_update(user_edit_data)

    _ = session.merge(user)
    session.commit()

    return UserRead.model_validate(user)
