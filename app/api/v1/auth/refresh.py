from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlmodel import Session

from db.session import get_db
from models.user import UserRead
from services.auth.refresh import refresh_access_token as refresh_service
from utils.auth import set_auth_cookie


router = APIRouter()


@router.post("/refresh")
def refresh_access_token(
    response: Response, # ⬅️ Response 주입
    db: Annotated[Session, Depends(get_db)],
    refresh_token: Annotated[str | None, Cookie()], # ⬅️ 쿠키에서 refresh_token 읽기
) -> UserRead:
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token not found")
    result = refresh_service(refresh_token, db)

    # 인증 쿠키 설정
    set_auth_cookie(
        response=response,
        access_token=result.access_token,
        refresh_token=result.refresh_token,
    )

    return UserRead.model_validate(result.user)
