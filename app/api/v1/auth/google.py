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
    param: Annotated[LoginWithGoogleCallbackParam, Depends()],
    db: Annotated[Session, Depends(get_db)],
) -> RedirectResponse:
    """
    구글로부터 전달받은 코드를 사용하여 사용자의 이름과 이메일을 가져옵니다.

    만약 사용자가 이미 가입되어 있다면, 로그인을 진행합니다.
    그렇지 않다면 Google로부터 받은 이름과 이메일로 User 테이블에 추가합니다.

    로그인이 완료되면 프론트엔드의 메인 페이지로 리다이렉트됩니다.

    TODO: 응답을 어떻게 프론트엔드로 전달할지는 아직 결정하지 못함
    """
    login = google_callback_service(param.code, db)

    # 프론트엔드로 리다이렉트
    response = RedirectResponse(url=settings.FRONTEND_URL, status_code=303)

    return response
