from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from sqlmodel import Session

from db.session import get_db
from errors.document import ForbiddenDocumentAccessError
from errors.general import IllegalStateError
from models.document import DocumentRead
from models.user import User
from services.document.get_docs_info import get_docs_info as docs_info_service
from utils.auth import get_current_user


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
                        "message": "문서를 찾을 수 없습니다."
                    }
                }
            }
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "문서에 접근할 권한이 없음",
            "model": ForbiddenDocumentAccessError
        }
    }
)
def get_docs_info(
    document_id: Annotated[int, Path(description="문서 ID")],
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)]
) -> DocumentRead:
    if current_user.user_id is None:
        raise IllegalStateError()

    docs = docs_info_service(
        document_id=document_id,
        user_id=current_user.user_id,
        session=session
    )

    return DocumentRead.model_validate(docs)
