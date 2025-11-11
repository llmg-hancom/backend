from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Response, status
from sqlmodel import Session

from core.config import settings
from db.session import get_db
from schemas.auth import LoginWithGoogleCallbackParam
from services.auth.google import (
    login_with_google_callback as google_callback_service,
)
from utils.auth import set_auth_cookie


router = APIRouter()


@router.get("/google", summary="구글 계정으로 로그인")
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


@router.get("/google/callback", summary="구글 계정 로그인 콜백")
def login_with_google_callback(
    response: Response,  # ⬅️ Response 주입
    param: Annotated[LoginWithGoogleCallbackParam, Depends()],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    # 액세스 토큰과 리프레시 토큰 발급
    login_result = google_callback_service(param.code, db)

    # 쿠키 설정
    set_auth_cookie(
        response=response,
        access_token=login_result.token,
        refresh_token=login_result.refresh_token,
    )

    frontend_url = f"{settings.FRONTEND_URL}/dashboard"

    response.status_code = status.HTTP_303_SEE_OTHER
    response.headers["Location"] = frontend_url

    return response
