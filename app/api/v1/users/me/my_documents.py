from typing import Annotated

from fastapi import APIRouter, Security

from models.document import DocumentRead
from models.user import User
from utils.auth import get_current_user


router = APIRouter()

@router.get(
    path="/documents",
    summary="현재 사용자의 문서 조회",
    tags=["문서"]
)
def get_user_documents(
    user: Annotated[User, Security(get_current_user)]
) -> list[DocumentRead]:
    return [
        DocumentRead.model_validate(doc)
        for doc in user.uploaded_documents
    ]
