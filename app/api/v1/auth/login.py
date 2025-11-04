from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from db.session import get_db
from schemas.auth import LoginRequest, LoginResponse
from services.auth.login import login as login_service

router = APIRouter()


@router.post(
    "/token",
    summary="로그인",
    responses={
        401: {
            "description": "이메일 또는 비밀번호가 일치하지 않는 경우",
            "content": {
                "application/json": {
                    "example": {"detail": "이메일 또는 비밀번호가 일치하지 않습니다."}
                }
            },
        }
    },
)
async def login(
    form_data: Annotated[LoginRequest, Depends()],
    db: Annotated[Session, Depends(get_db)],
) -> LoginResponse:
    """
    이메일과 비밀번호를 확인해 올바른 경우 JWT 토큰을 발급합니다.
    """
    try:
        result = login_service(form_data.username, form_data.password, db)
        return LoginResponse(
            access_token=result.token, token_type=result.token_type, user=result.user
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
