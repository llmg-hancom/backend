from fastapi import Depends, APIRouter
from typing import Annotated
from utils.auth import get_current_user
from models.user import UserRead, User

router = APIRouter()


@router.get("/me", response_model=UserRead)
def get_user_info(
    user: Annotated[User, Depends(get_current_user)],
) -> UserRead:
    return UserRead.model_validate(user)
