from typing import Annotated

from fastapi import APIRouter, Body, Depends, status
from sqlmodel import Session

from db.session import get_db
from models.user import User
from schemas.auth import ChangePasswordRequest
from services.users.change_my_password import change_my_password as service
from utils.auth import get_current_user


router = APIRouter()

@router.patch(
    path="/password",
    summary="유저 비밀번호 변경",
    status_code=status.HTTP_204_NO_CONTENT
)
def change_password(
    current_user: Annotated[User, Depends(get_current_user)],
    body: Annotated[ChangePasswordRequest, Body()],
    session: Annotated[Session, Depends(get_db)]
) -> None:
    service(
        change_user=current_user,
        old_password=body.current_password,
        new_password=body.new_password,
        session=session
    )
