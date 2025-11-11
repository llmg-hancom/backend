from fastapi import APIRouter

from .upload import router as upload_router


router = APIRouter(prefix="/document", tags=["문서"])

router.include_router(upload_router)
