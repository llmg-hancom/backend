from fastapi import APIRouter


router = APIRouter()

@router.post(
    path="/",
    summary="문서 업로드",
)
def upload_documents():
    raise NotImplementedError()
