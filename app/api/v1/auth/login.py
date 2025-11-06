from typing import Annotated

from fastapi import APIRouter, Depends
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
            "description": "이메일 또는 비밀번호가 일치하지 않거나 계정이 비활성화된 경우",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_credentials": {
                            "summary": "잘못된 인증 정보",
                            "value": {
                                "detail": "아이디 또는 비밀번호가 잘못되었습니다."
                            },
                        },
                        "user_inactive": {
                            "summary": "비활성화된 계정",
                            "value": {"detail": "사용자 계정이 비활성화되었습니다."},
                        },
                    }
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
    result = login_service(form_data.username, form_data.password, db)
    return LoginResponse(
        access_token=result.token,
        refresh_token=result.refresh_token,
        token_type=result.token_type,
        user=result.user
    )
