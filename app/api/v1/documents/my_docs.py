from typing import Annotated

from fastapi import APIRouter, Security

from models.document import DocumentRead
from models.user import User
from utils.auth import get_current_user


router = APIRouter(prefix="/documents")


@router.get(
    path="",
    summary="내 문서 목록 조회",
    deprecated=True
)
def my_documents(
    current_user: Annotated[User, Security(get_current_user)],
) -> list[DocumentRead]:
    return [
        DocumentRead.model_validate(doc)
        for doc in current_user.uploaded_documents
        if doc.deleted_at is None  # 삭제되지 않은 문서만 반환
    ]
