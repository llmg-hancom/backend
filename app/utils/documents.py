from typing import Annotated

from fastapi import Depends, Path
from sqlmodel import Session, select

from db.session import get_db
from errors.document import DocumentNotFoundError
from errors.general import IllegalStateError
from models.document import Document
from models.user import User
from utils.auth import get_current_user


def get_document_from_document_id_path(
    document_id: Annotated[int, Path(description="문서 ID")],
    session: Annotated[Session, Depends(get_db)],
) -> Document:
    """
    경로 매개변수에 명시된 문서 ID로 문서를 가져옵니다.
    해당 문서가 존재하지 않는다면 오류를 발생시킵니다.
    """
    doc = session.exec(select(Document).where(Document.document_id == document_id)).one_or_none()

    # 문서가 존재하지 않는 경우
    if doc is None:
        raise DocumentNotFoundError()

    # 해당 문서의 deleted_at 필드가 존재하는 경우
    if doc.deleted_at is not None:
        raise DocumentNotFoundError()

    return doc


def require_document_owner(
    document: Annotated[Document, Depends(get_document_from_document_id_path)],
    user: Annotated[User, Depends(get_current_user)],
) -> Document:
    """
    경로 매개변수에 명시된 문서가 현재 사용자의 문서가 맞는지 확인하고,
    맞을 경우 문서를 반환합니다.
    문서 소유자가 아니라면 오류를 발생시킵니다.
    """
    if user.user_id is None:
        raise IllegalStateError()

    if document.uploaded_by_user_id != user.user_id:
        raise DocumentNotFoundError()

    return document
