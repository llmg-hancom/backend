from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Response, status
from sqlmodel import Session

from core.config import settings
from db.session import get_db
from models.user import UserRead
from schemas.auth import GoogleLoginRequest
from services.auth.google import (
    login_with_google_callback as google_callback_service,
)
from utils.auth import set_auth_cookie


router = APIRouter()


@router.get(path="/google", summary="구글 계정으로 로그인")
async def login_with_google():
    """
    구글 로그인 페이지 링크를 반환합니다.
    """
    param = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
    }

    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(param)}"
    return {"url": url}


@router.post(
    path="/google/callback",
    summary="구글 로그인 (API 방식)",
    status_code=status.HTTP_200_OK,
)
def login_with_google_api(
    response: Response,
    request: GoogleLoginRequest,  # 프론트에서 body로 code를 받음
    db: Annotated[Session, Depends(get_db)],
) -> UserRead:
    # 1. 서비스 로직 호출 (기존 로직 재사용)
    # 서비스 함수는 code와 db를 받아 토큰을 생성합니다.
    login_result = google_callback_service(request.code, db)

    # 2. 쿠키 설정 (200 OK 응답이므로 브라우저가 확실히 저장함)
    set_auth_cookie(
        response=response,
        access_token=login_result.token,
        refresh_token=login_result.refresh_token,
    )

    # 3. 사용자 정보 반환 (선택 사항)
    return UserRead.model_validate(login_result.user)