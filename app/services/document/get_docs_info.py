from sqlmodel import Session, select, col

from errors.document import DocumentNotFoundError, ForbiddenDocumentAccessError
from models.document import Document


def get_docs_info(user_id: int, document_id: int, session: Session) -> Document:
    statement = (
        select(Document)
        .where(Document.document_id == document_id)
        .where(col(Document.deleted_at).is_(None))
    )
    document = session.exec(statement).one_or_none()

    # 해당 문서가 존재하지 않는 경우
    if document is None:
        raise DocumentNotFoundError()

    # 해당 문서를 조회할 권한이 없는 경우
    if document.uploaded_by_user_id != user_id:
        raise ForbiddenDocumentAccessError()

    return document
