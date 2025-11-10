from typing import Annotated

from fastapi import APIRouter, Depends, Path

from models.user import User
from utils.auth import get_current_user


router = APIRouter()

@router.delete(
    path="/{group_id}/members/{member_id}",
    summary="그룹에서 유저 탈퇴"
)
async def remove_group_member(
    user: Annotated[User, Depends(get_current_user)],
    group_id: Annotated[int, Path()],
    member_id: Annotated[int, Path()]
):
    raise NotImplementedError()
