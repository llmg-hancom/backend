from typing import Annotated

from fastapi import APIRouter, Response, status, Depends, Cookie
from sqlmodel import Session

from db.session import get_db
from services.auth.logout import delete_token
from utils.auth import delete_auth_cookie

# 💡 login.py 또는 별도 파일에 추가
router = APIRouter()


@router.delete("/token", summary="로그아웃", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    refresh_token: Annotated[str | None, Cookie()],
) -> None:
    """
    HttpOnly 쿠키(access_token, refresh_token)를 삭제합니다.
    """
    if refresh_token is not None:
        delete_token(refresh_token=refresh_token, db=db)
        delete_auth_cookie(response=response)
        db.flush()

    response.status_code = status.HTTP_204_NO_CONTENT

    return None
