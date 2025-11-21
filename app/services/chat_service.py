from typing import Annotated, Self

from fastapi import Depends, Security
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from db.session import get_async_db
from errors.document import DocumentNotFoundError, ForbiddenDocumentAccessError
from errors.general import IllegalStateError
from models import ChatSpace, ChatSpaceDocument, Document, User
from utils.auth import get_current_user


class ChatService:
    db: AsyncSession
    actor: User

    def __init__(self, actor: User, db: AsyncSession):
        # actor 객체가 데이터베이스에서 불러온 것이라면
        # PRIMARY KEY는 데이터베이스에서 자동으로 추가되므로
        # user_id가 None일 수 없음
        if actor.user_id is None:
            raise IllegalStateError()

        self.actor = actor
        self.db = db

    @classmethod
    def factory(
        cls,
        actor: Annotated[User, Security(get_current_user)],
        db: Annotated[AsyncSession, Depends(get_async_db)]
    ) -> Self:
        return cls(actor, db)

    async def add_document(self, space_id: int, document_ids: set[int]):
        """
        챗스페이스에 문서를 추가합니다.
        """
        # 리스트가 비어있는 경우
        if len(document_ids) == 0:
            return

        # 타입 내로잉
        if self.actor.user_id is None:
            raise IllegalStateError()

        # actor가 해당 문서에 대해 권한이 있는지 검사합니다.
        query = (
            select(Document)
            .where(col(Document.document_id).in_(document_ids))
            .where(Document.uploaded_by_user_id == self.actor.user_id)
        )

        actor_own_documents = (await self.db.execute(query)).scalars().all()

        # 하나라도 권한이 없는 문서가 있다면 전체 실패
        if len(actor_own_documents) != len(document_ids):
            raise ForbiddenDocumentAccessError()

        bridges = [
            ChatSpaceDocument(
                space_id=space_id,
                document_id=document.document_id,
                added_by_user_id=self.actor.user_id
            )
            for document in actor_own_documents

            # 타입 내로잉
            if document.document_id is not None
        ]

        self.db.add_all(bridges)
        await self.db.commit()


    async def delete_document(self, space_id: int, document_ids: set[int]) -> None:
        """
        챗스페이스에 연결된 문서를 연결 해제합니다.
        """
        query = (
            select(ChatSpaceDocument)
            .where(ChatSpaceDocument.space_id == space_id)
            .where(col(ChatSpaceDocument.document_id).in_(document_ids))
        )

        bridge = (await self.db.execute(query)).all()

        # 하나라도 연결 안된 문서가 있다면 전체 실패
        if len(bridge) != len(document_ids):
            raise DocumentNotFoundError()

        await self.db.delete(bridge)
        await self.db.commit()
