from fastapi import APIRouter

# router
from .auth import router as auth_router

router = APIRouter(prefix="/v1")

router.include_router(auth_router)
