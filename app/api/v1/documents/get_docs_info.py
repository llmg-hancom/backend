from typing import Annotated

from fastapi import APIRouter, status, Security

from models.document import Document, DocumentRead
from utils.documents import require_document_owner


router = APIRouter()


@router.get(
    path="/{document_id}",
    summary="문서 정보 조회",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "문서를 찾을 수 없음",
            "content": {
                "application/json": {
                    "example": {
                        "status_code": 404,
                        "error_code": "DOCUMENT_NOT_FOUND",
                        "message": "문서를 찾을 수 없습니다.",
                    }
                }
            },
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "문서에 접근할 권한이 없음",
            "content": {
                "application/json": {
                    "example": {
                        "status_code": 403,
                        "error_code": "FORBIDDEN_DOCUMENT_ACCESS",
                        "message": "문서에 접근할 권한이 없습니다.",
                    }
                }
            },
        },
    },
)
def get_docs_info(
    doc: Annotated[Document, Security(require_document_owner)],
) -> DocumentRead:
    return DocumentRead.model_validate(doc)
