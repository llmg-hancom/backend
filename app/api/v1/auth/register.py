from fastapi import APIRouter, Body, Depends, HTTPException
from sqlmodel import Session
from starlette import status

from db.session import get_db
from models.user import UserRead
from schemas.auth import RegisterRequest
from services.auth.register import register as register_service

router = APIRouter()


@router.post(
    "/register",
    summary="회원가입",
    responses={
        400: {
            "description": "이미 가입된 이메일인 경우",
            "content": {
                "application/json": {"example": {"detail": "이미 가입된 이메일입니다."}}
            },
        }
    },
)
async def register(
    body: RegisterRequest = Body(...), db: Session = Depends(get_db)
) -> UserRead:
    """
    회원가입
    """

    try:
        result = register_service(
            email=body.email, password=body.password, nickname=body.nickname, db=db
        )
        return UserRead.model_validate(result.user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
