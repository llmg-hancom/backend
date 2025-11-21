from sqlalchemy.ext.asyncio import AsyncSession

from errors.general import IllegalStateError
from models import ChatSpace, ChatSpaceDocument


async def add_documents_to_chat_space(
    space: ChatSpace,
    doc_ids: list[int],
    add_user_id: int,
    session: AsyncSession,
):
    if space.space_id is None:
        raise IllegalStateError()

    chat_space_docs = [
        ChatSpaceDocument(
            space_id=space.space_id,
            document_id=doc_id,
            added_by_user_id=add_user_id,
        )
        for doc_id in doc_ids
    ]

    session.add_all(chat_space_docs)
    await session.commit()
