from typing import Annotated

from fastapi import APIRouter, Security

from errors.general import IllegalStateError  # noqa: F401
from models.user import User
from schemas.groups import GroupRead
from utils.auth import get_current_user


router = APIRouter(prefix="/groups")


@router.get("", deprecated=True)
def my_group(
    user: Annotated[User, Security(get_current_user)],
) -> list[GroupRead]:
    memberships = user.group_memberships

    joined_groups = [
        GroupRead.model_validate(membership.group) for membership in memberships
    ]

    return joined_groups
