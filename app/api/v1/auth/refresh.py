from typing import Annotated

from fastapi import APIRouter, Depends, Response, Cookie, HTTPException
from sqlmodel import Session
from models.user import UserRead

from db.session import get_db
from core.config import settings
from schemas.auth import LoginResponse, TokenRefreshRequest
from services.auth.refresh import refresh_access_token as refresh_service


router = APIRouter()


@router.post("/refresh")
def refresh_access_token(
    response: Response, # ⬅️ Response 주입
    db: Annotated[Session, Depends(get_db)],
    refresh_token: Annotated[str | None, Cookie()] = None, # ⬅️ 쿠키에서 refresh_token 읽기
) -> UserRead:
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token not found")
    result = refresh_service(refresh_token, db)

    response.set_cookie(
        key="access_token",
        value=result.token,
        httponly=True,
        secure=settings.COOKIE_SECURE,  # ⬅️ (프로덕션=True, 로컬=False)
        samesite="lax",  # ⬅️ 'strict' 또는 'lax'
        path="/",
        max_age=settings.JWT_EXPIRE_HOURS * 60 * 60,  # ⬅️ (만료 시간 설정)
    )

    # 🚨 (선택적) Refresh Token도 갱신(Rotate)하는 경우
    response.set_cookie(
        key="refresh_token",
        value=result.refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        path="/",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAY * 24 * 60 * 60,
    )

    return UserRead.model_validate(result.user)
