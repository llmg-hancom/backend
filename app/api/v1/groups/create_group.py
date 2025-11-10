from typing import Annotated

from fastapi import APIRouter, Body, Depends
from sqlmodel import Session

from db.session import get_db
from models.group import Group
from models.group_member import GroupMember
from models.user import User
from schemas.groups import GroupCreate, GroupRead
from utils.auth import get_current_user


router = APIRouter()

@router.post("/", status_code=201)
def create_group(
    body: Annotated[GroupCreate, Body()],
    db: Annotated[Session, Depends(get_db)],
    request_user: Annotated[User, Depends(get_current_user)]
) -> GroupRead:
    if request_user.user_id is None:
        raise RuntimeError("데이터베이스에서 불러온 User의 user_id가 None입니다.")

    group = Group(
        group_name=body.group_name,
        description=body.description,
        created_by_user_id=request_user.user_id
    )

    user_group_rel = GroupMember(
        user_id=request_user.user_id,
        group_id=group.id
    )

    db.add(group)
    db.add(user_group_rel)
    db.commit()

    return GroupRead.model_validate(group)
