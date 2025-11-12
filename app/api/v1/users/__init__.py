from fastapi import APIRouter

# routes
from .me import router as me_router


router = APIRouter(prefix="/users", tags=["사용자"])
router.include_router(me_router)
