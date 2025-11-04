from fastapi import APIRouter

# routes
from .me.info import router as my_info_router


router = APIRouter(prefix="/users", tags=["사용자"])
router.include_router(my_info_router)
