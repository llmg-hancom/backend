from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlmodel import Session

from core.config import settings
from db.session import get_db
from models.user import UserRead
from schemas.auth import LoginRequest
from services.auth.login import login as login_service
from utils.auth import set_auth_cookie


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
    response: Response,  # ⬅️ Response 객체 주입
    form_data: Annotated[LoginRequest, Depends()],
    db: Annotated[Session, Depends(get_db)],
) -> UserRead:
    """
    이메일과 비밀번호를 확인해 올바른 경우 JWT 토큰을 발급합니다.
    """
    result = login_service(form_data.username, form_data.password, db)

    # 인증 쿠키 설정
    set_auth_cookie(
        response=response,
        access_token=result.token,
        refresh_token=result.refresh_token,
    )

    return UserRead.model_validate(result.user)
