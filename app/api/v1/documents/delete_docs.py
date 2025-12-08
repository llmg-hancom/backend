from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Security, status
from sqlalchemy import delete
from sqlmodel import Session, col

from db.session import get_db
from models import ChatSpaceDocument
from models.document import Document
from utils.documents import require_document_owner


router = APIRouter()


@router.delete(
    path="/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_204_NO_CONTENT: {
            "description": "문서 삭제 성공",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "문서가 존재하지 않음",
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
            "description": "문서를 열람할 권한이 없음",
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
def delete_documents(
    doc: Annotated[Document, Security(require_document_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """
    Document 객체의 deleted_at 속성을 현재 시간으로 추가합니다.
    """
    # 챗스페이스와의 연결은 즉시 제거
    db.exec(
        delete(ChatSpaceDocument).where(
            col(ChatSpaceDocument.document_id) == doc.document_id
        )
    )
    doc.deleted_at = datetime.now(tz=timezone.utc)
    db.add(doc)
