from fastapi import APIRouter

router = APIRouter()


@router.get("/google", summary="구글 계정으로 로그인")
async def login_with_google():
    pass


@router.get("/google/callback", summary="구글 계정 로그인 콜백")
async def login_with_google_callback():
    pass
