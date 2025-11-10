from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, status
from sqlmodel import Session

from db.session import get_db
from models.user import User
from schemas.groups import GroupUserInviteRequest
from services.group.invite_user import invite_user as invite_service
from utils.auth import get_current_user


router = APIRouter()

@router.post(
    path="/{group_id}/members",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="그룹에 유저 초대",
    responses={
        204: {},
        400: {
            "description": "유저가 이미 있거나 가입시키려는 유저가 존재하지 않는 경우",
            "content": {
                "application/json": {
                    "examples": {
                        "user_not_exist": {
                            "summary": "사용자가 존재하지 않음",
                            "value": {"detail": "초대하려는 유저는 존재하지 않습니다."},
                        },
                        "user_already_in_group": {
                            "summary": "이미 그룹에 속한 유저",
                            "value": {"detail": "초대하려는 유저는 이미 그룹에 있습니다."},
                        },
                    }
                }
            }
        }
    }
)
def invite(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    group_id: Annotated[int, Path()],
    body: Annotated[GroupUserInviteRequest, Body()]
) -> None:
    invite_service(
        inviter=user,
        session=db,
        group_id=group_id,
        body=body
    )
