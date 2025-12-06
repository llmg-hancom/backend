from fastapi import APIRouter

# router
from .auth import router as auth_router
from .chat import router as chat_router
from .documents import router as documents_router
from .groups import router as groups_router
from .health import router as health_router
from .users import router as users_router


router = APIRouter(prefix="/v1")
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(users_router)
router.include_router(groups_router)
router.include_router(documents_router)
router.include_router(chat_router)
