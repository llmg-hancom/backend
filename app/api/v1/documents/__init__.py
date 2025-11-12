from fastapi import APIRouter

from .get_docs_info import router as get_docs_info_router
from .my_docs import router as my_docs_router
from .upload import router as upload_router


router = APIRouter(prefix="/documents", tags=["문서"])

router.include_router(upload_router)
router.include_router(my_docs_router)
router.include_router(get_docs_info_router)
