from fastapi import APIRouter, Response

# 💡 login.py 또는 별도 파일에 추가
router = APIRouter()


@router.post("/logout", summary="로그아웃")
def logout(response: Response):
    """
    HttpOnly 쿠키(access_token, refresh_token)를 삭제합니다.
    """
    response.delete_cookie(key="access_token", path="/", httponly=True)
    response.delete_cookie(key="refresh_token", path="/", httponly=True)
    return {"message": "Logged out successfully"}