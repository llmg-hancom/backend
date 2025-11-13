from fastapi import APIRouter

from .change_password import router as change_password_router
from .edit_info import router as edit_info_router
from .info import router as info_router
from .my_groups import router as my_groups_router


router = APIRouter(prefix="/me")

router.include_router(edit_info_router)
router.include_router(info_router)
router.include_router(change_password_router)
router.include_router(my_groups_router)
