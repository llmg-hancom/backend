from fastapi import APIRouter

from .edit_info import router as edit_info_router
from .info import router as info_router


router = APIRouter(prefix="/me")

router.include_router(edit_info_router)
router.include_router(info_router)
