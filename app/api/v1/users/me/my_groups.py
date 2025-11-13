from typing import Annotated

from fastapi import APIRouter, Security

from models.user import User, UserRead
from schemas.groups import GroupReadWithoutMembers
from utils.auth import get_current_user


router = APIRouter()

@router.get(
    path="/groups",
    summary="현재 사용자가 소속된 그룹 조회",
    tags=["그룹"]
)
def my_groups(
    user: Annotated[User, Security(get_current_user)],
) -> list[GroupReadWithoutMembers]:
    return [
        GroupReadWithoutMembers(
            group_id=group.group.group_id,
            group_name=group.group.group_name,
            created_at=group.group.created_at,
            created_by_user=UserRead.model_validate(group.group.created_by_user),
        )
        for group in user.group_memberships
        if group.group.group_id is not None
    ]
