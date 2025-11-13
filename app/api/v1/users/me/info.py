from typing import Annotated

from fastapi import APIRouter, Security

from models.user import User, UserRead
from utils.auth import get_current_user


router = APIRouter()


@router.get("/", response_model=UserRead)
def get_user_info(
    user: Annotated[User, Security(get_current_user)],
) -> UserRead:
    return UserRead.model_validate(user)
