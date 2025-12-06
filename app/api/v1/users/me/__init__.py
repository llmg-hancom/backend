from fastapi import APIRouter

from .change_password import router as change_password_router
from .get_user_space import router as my_space_router
from .info import router as info_router
from .my_documents import router as my_documents_router
from .my_groups import router as my_groups_router


router = APIRouter()

router.include_router(info_router)
router.include_router(change_password_router, prefix="/me")
router.include_router(my_groups_router, prefix="/me")
router.include_router(my_documents_router, prefix="/me")
router.include_router(my_space_router, prefix="/me")
