from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path
from sqlmodel import Session

from db.session import get_db
from models.user import User
from schemas.groups import GroupUserInvite
from utils.auth import get_current_user


router = APIRouter()

@router.post("/{group_id}/members")
def invite(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    group_id: Annotated[int, Path()],
    body: Annotated[GroupUserInvite, Body()]
) -> None:
    raise NotImplementedError()
