from fastapi import APIRouter

from .sessions import router as sessions_router
from .spaces import router as spaces_router
from .stream import router as stream_router


router = APIRouter(prefix="/chat", tags=["채팅"])

router.include_router(sessions_router)
router.include_router(stream_router)
router.include_router(spaces_router)
