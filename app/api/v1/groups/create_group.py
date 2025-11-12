from typing import Annotated

from fastapi import APIRouter, Body, Depends, status, Security
from sqlmodel import Session

from db.session import get_db
from models.user import User
from schemas.groups import GroupCreate, GroupRead
from services.group.create_group import create_group as create_group_service
from utils.auth import get_current_user


router = APIRouter()


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_group(
    body: Annotated[GroupCreate, Body()],
    db: Annotated[Session, Depends(get_db)],
    request_user: Annotated[User, Security(get_current_user)],
) -> GroupRead:
    return create_group_service(request_user=request_user, db=db, body=body)
