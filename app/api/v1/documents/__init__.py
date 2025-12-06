from fastapi import APIRouter

from .delete_docs import router as delete_docs_router
from .get_docs_info import router as get_docs_info_router
from .my_docs import router as my_docs_router
from .upload import router as upload_router


router = APIRouter()

router.include_router(upload_router, tags=["문서"])
router.include_router(my_docs_router, tags=["문서"])
router.include_router(get_docs_info_router, prefix="/documents", tags=["문서"])
router.include_router(delete_docs_router, prefix="/documents", tags=["문서"])
