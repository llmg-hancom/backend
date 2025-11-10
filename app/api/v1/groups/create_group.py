from typing import Annotated

from fastapi import APIRouter, Body, Depends
from sqlmodel import Session

from db.session import get_db
from models.group import Group
from models.group_member import GroupMember
from models.user import User
from schemas.groups import GroupCreate, GroupRead
from services.group.create_group import create_group as create_group_service
from utils.auth import get_current_user


router = APIRouter()

@router.post("/", status_code=201)
def create_group(
    body: Annotated[GroupCreate, Body()],
    db: Annotated[Session, Depends(get_db)],
    request_user: Annotated[User, Depends(get_current_user)]
) -> GroupRead:
    return create_group_service(
        request_user=request_user,
        db=db,
        body=body
    )
