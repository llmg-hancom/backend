from typing import Annotated

from fastapi import APIRouter, Security

from errors.general import IllegalStateError  # noqa: F401
from models.user import User, UserRead
from schemas.groups import GroupRead
from utils.auth import get_current_user


router = APIRouter()


@router.get("/")
def my_group(
    user: Annotated[User, Security(get_current_user)],
) -> list[GroupRead]:
    joined_group = user.group_memberships

    return [
        GroupRead(
            group_name=rel.group.group_name,
            group_id=rel.group.group_id,
            created_at=rel.group.created_at,
            created_by_user=UserRead.model_validate(rel.group.created_by_user),
            members=[
                UserRead.model_validate(member.user) for member in rel.group.members
            ],
        )
        for rel in joined_group
        if rel.group.group_id is not None
    ]
