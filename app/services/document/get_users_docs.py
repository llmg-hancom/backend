from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from errors.general import IllegalStateError
from models.document import Document
from models.user import User


async def get_users_documents(
    offset: int, limit: int, user: User, session: AsyncSession
) -> list[Document]:
    if user.user_id is None:
        raise IllegalStateError()

    query = (
        select(Document)
        .where(Document.uploaded_by_user_id == user.user_id)
        .where(Document.deleted_at is not None)
        .offset(offset)
        .limit(limit)
    )

    data = (await session.exec(query)).all()
    return [d for d in data]
