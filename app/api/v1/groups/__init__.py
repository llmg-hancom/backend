from fastapi import APIRouter

from .create_group import router as create_group_router
from .group_invite import router as invite_router
from .my_group import router as my_group_router
from .remove_group_member import router as remove_group_member_router


router = APIRouter(prefix="/groups", tags=["Groups"])

router.include_router(create_group_router)
router.include_router(my_group_router)
router.include_router(invite_router)
router.include_router(remove_group_member_router)
