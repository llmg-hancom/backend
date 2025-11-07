from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlmodel import Session

from core.config import settings
from db.session import get_db
from schemas.auth import LoginWithGoogleCallbackParam
from services.auth.google import (
    login_with_google_callback as google_callback_service,
)
from starlette import status

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
    response: RedirectResponse,  # ⬅️ Response 주입
    param: Annotated[LoginWithGoogleCallbackParam, Depends()],
    db: Annotated[Session, Depends(get_db)],
) -> RedirectResponse:
    # 1. (login_service와 유사하게) 토큰과 유저 정보가 포함된 result 반환
    login_result = google_callback_service(param.code, db)

    # 2. 🚨 백엔드 응답에 직접 쿠키 설정
    response.set_cookie(
        key="access_token",
        value=login_result.access_token,
        httponly=True,
        # ... (login.py와 동일한 옵션) ...
    )
    response.set_cookie(
        key="refresh_token",
        value=login_result.refresh_token,
        httponly=True,
        # ... (login.py와 동일한 옵션) ...
    )

    # 3. 💡 프론트엔드의 로그인 페이지(/auth/callback)가 아닌,
    #    로그인 후 페이지(예: /dashboard)로 바로 리다이렉트
    frontend_url = f"{settings.FRONTEND_URL}/dashboard"

    # ❗️ RedirectResponse를 직접 생성하지 않고, response 객체를 사용해야 쿠키가 설정됩니다.
    #    따라서 RedirectResponse를 반환하는 대신, response의 헤더와 상태 코드를 설정합니다.
    response.status_code = status.HTTP_303_SEE_OTHER
    response.headers["Location"] = frontend_url
    return response # ⬅️ 쿠키가 설정된 response 반환
