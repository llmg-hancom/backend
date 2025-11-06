from fastapi import APIRouter
# routers
from .google import router as google_router
from .login import router as login_router
from .refresh import router as refresh_router
from .register import router as register_router


router = APIRouter(prefix="/auth", tags=["인증"])
router.include_router(register_router)
router.include_router(login_router)
router.include_router(google_router)
router.include_router(refresh_router)
