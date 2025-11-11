from typing import Annotated

from fastapi import APIRouter, Body, Depends, status
from sqlmodel import Session

from db.session import get_db
from models.user import UserRead
from schemas.auth import RegisterRequest
from services.auth.register import register as register_service


router = APIRouter()


@router.post(
    "/register",
    summary="회원가입",
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "이미 가입된 이메일인 경우",
            "content": {
                "application/json": {"example": {"detail": "이미 가입된 이메일입니다."}}
            },
        }
    },
)
async def register(
    body: Annotated[RegisterRequest, Body()], db: Annotated[Session, Depends(get_db)]
) -> UserRead:
    """
    회원가입
    """

    result = register_service(
        email=body.email, password=body.password, nickname=body.nickname, db=db
    )
    return UserRead.model_validate(result.user)
