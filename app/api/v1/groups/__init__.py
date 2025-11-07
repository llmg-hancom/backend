from fastapi import APIRouter

from .create_group import router as create_group_router


router = APIRouter(prefix="/groups", tags=["Groups"])

router.include_router(create_group_router)
