from typing import Annotated

from fastapi import APIRouter, Body, Depends, status, Security
from sqlmodel import Session

from db.session import get_db
from models.group import Group
from models.user import User
from schemas.groups import GroupUserInviteRequest
from services.group.invite_user import invite_user as invite_service
from utils.auth import get_current_user
from utils.group import require_group_admin


router = APIRouter()


@router.post(
    path="/{group_id}/members",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="그룹에 유저 초대",
    responses={
        status.HTTP_204_NO_CONTENT: {},
        status.HTTP_400_BAD_REQUEST: {
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
                            "value": {
                                "detail": "초대하려는 유저는 이미 그룹에 있습니다."
                            },
                        },
                    }
                }
            },
        },
    },
)
def invite(
    user: Annotated[User, Security(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    group: Annotated[Group, Security(require_group_admin)],
    body: Annotated[GroupUserInviteRequest, Body()],
) -> None:
    invite_service(inviter=user, session=db, group=group, body=body)
