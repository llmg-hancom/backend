from typing import Annotated

from fastapi import APIRouter, Depends

from models.user import User
from schemas.groups import GroupRead
from utils.auth import get_current_user


router = APIRouter()

@router.get("/")
def my_group(
    user: Annotated[User, Depends(get_current_user)],
) -> list[GroupRead]:
    joined_group = user.group_memberships

    return [GroupRead.model_validate(rel.group) for rel in joined_group]
