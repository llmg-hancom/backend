from fastapi import APIRouter

from .my_docs import router as my_docs_router
from .upload import router as upload_router


router = APIRouter(prefix="/document", tags=["문서"])

router.include_router(upload_router)
router.include_router(my_docs_router)
