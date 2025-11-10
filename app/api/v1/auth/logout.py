from fastapi import APIRouter, Response, status

from utils.auth import set_auth_cookie


# 💡 login.py 또는 별도 파일에 추가
router = APIRouter()


@router.delete("/token", summary="로그아웃", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    """
    HttpOnly 쿠키(access_token, refresh_token)를 삭제합니다.
    """

    set_auth_cookie(
        response=response,
        access_token="",
        refresh_token=""
    )

    response.status_code = 204

    return None
