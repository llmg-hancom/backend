from fastapi import APIRouter

from .create_group import router as create_group_router
from .get_group_info import router as get_group_info_router
from .group_chat_space import router as group_chat_space_router
from .group_invite import router as invite_router
from .my_group import router as my_group_router
from .remove_group_member import router as remove_group_member_router


router = APIRouter()

router.include_router(create_group_router, tags=["그룹"])
router.include_router(my_group_router, tags=["그룹"])
router.include_router(invite_router, prefix="/groups", tags=["그룹"])
router.include_router(remove_group_member_router, prefix="/groups", tags=["그룹"])
router.include_router(group_chat_space_router, prefix="/groups", tags=["그룹", "채팅"])
router.include_router(get_group_info_router, prefix="/groups", tags=["그룹"])
