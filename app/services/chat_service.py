from datetime import datetime, timezone
from typing import Annotated, Self

from fastapi import Depends, Security
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, exists, literal, select

from db.session import get_async_db
from errors.chat import (
    ForbiddenSpaceAccessError,
)
from errors.document import DocumentNotFoundError, ForbiddenDocumentAccessError
from errors.general import IllegalStateError
from errors.groups import UserIsNotGroupAdminError, UserIsNotGroupMemberError
from errors.space import SpaceNotFoundError
from models import (
    ChatSession,
    ChatSpace,
    ChatSpaceDocument,
    Document,
    Group,
    GroupMember,
    User,
)
from models.group_member import UserRole
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
        db: Annotated[AsyncSession, Depends(get_async_db)],
    ) -> Self:
        return cls(actor, db)


    async def create_chat_space(self, name: str) -> ChatSpace:
        """
        챗스페이스를 추가합니다.
        """
        if self.actor.user_id is None:
            raise IllegalStateError()

        space = ChatSpace(name=name, owner_user_id=self.actor.user_id)

        self.db.add(space)
        await self.db.commit()
        await self.db.refresh(space)

        return space


    async def create_group_chat_space(self, group: Group, name: str) -> ChatSpace:
        """
        그룹에 속한 챗스페이스를 생성합니다.
        """
        if self.actor.user_id is None:
            raise IllegalStateError()

        if group.group_id is None:
            raise IllegalStateError()

        # actor가 그룹 admin인지 검사
        query = select(
            exists(GroupMember)
            .where(col(GroupMember.group_id) == group.group_id)
            .where(col(GroupMember.user_id) == self.actor.user_id)
            .where(col(GroupMember.role) == UserRole.admin)
        )

        if not await self.db.scalar(query):
            raise UserIsNotGroupAdminError()

        space = ChatSpace(name=name, group_id=group.group_id)

        self.db.add(space)
        await self.db.commit()
        await self.db.refresh(space)

        return space


    async def get_group_chat_spaces(self, group: Group, offset: int, limit: int) -> list[ChatSpace]:
        """
        그룹에 속한 챗스페이스의 목록을 조회합니다.
        """
        # actor가 해당 그룹의 멤버인지 확인
        member_query = select(
            exists(GroupMember)
            .where(col(GroupMember.group_id) == group.group_id)
            .where(col(GroupMember.user_id) == self.actor.user_id)
        )

        if not await self.db.scalar(member_query):
            raise UserIsNotGroupMemberError()

        query = (
            select(ChatSpace)
            .where(col(ChatSpace.group_id) == group.group_id)
            .where(col(ChatSpace.deleted_at).is_(None))
            .offset(offset)
            .limit(limit)
        )

        spaces = (await self.db.scalars(query)).all()
        return [space for space in spaces]


    async def delete_chat_space(self, space_id: int) -> None:
        """
        챗스페이스를 삭제합니다.
        """
        if self.actor.user_id is None:
            raise IllegalStateError()

        query = (
            select(ChatSpace)
            .where(col(ChatSpace.space_id) == space_id)
            .where(col(ChatSpace.deleted_at).is_(None))
        )

        space = (await self.db.execute(query)).scalar_one_or_none()

        if space is None:
            raise SpaceNotFoundError(space_id=space_id)

        if space.owner_user_id != self.actor.user_id:
            raise ForbiddenSpaceAccessError()

        space.deleted_at = datetime.now(tz=timezone.utc)


    async def get_chat_space_documents(
        self, space_id: int, offset: int, limit: int
    ) -> list[Document]:
        """
        현재 챗 스페이스에 연결된 문서 목록을 조회합니다.
        """
        # [수정] ChatSpaceDocument가 아니라 Document를 바로 조회합니다.
        query = (
            select(Document)
            .join(
                ChatSpaceDocument, Document.document_id == ChatSpaceDocument.document_id
            )
            .where(ChatSpaceDocument.space_id == space_id)
            .offset(offset)
            .limit(limit)
        )

        # 이제 result는 이미 Document 객체들의 리스트입니다.
        result = (await self.db.execute(query)).scalars().all()

        return list(result)


    async def add_document(self, space: ChatSpace, document_ids: set[int]):
        """
        챗스페이스에 문서를 추가합니다. 개인 챗스페이스일 경우 스페이스를 생성한 사람이,
        그룹 챗스페이스일 경우 스페이스를 소유한 그룹의 admin이 문서를 추가할 수 있습니다.
        """
        # 리스트가 비어있는 경우
        if len(document_ids) == 0:
            return

        # 타입 내로잉
        if self.actor.user_id is None:
            raise IllegalStateError()

        if space.space_id is None:
            raise IllegalStateError()

        # 개인 챗스페이스이고, actor가 스페이스를 생성한 사람이 아닌 경우
        if space.owner_user_id is not None and space.owner_user_id != self.actor.user_id:
            raise ForbiddenSpaceAccessError()

        # 그룹 챗스페이스이고, actor가 그 그룹의 admin이 아닌 경우
        if space.group_id is not None:
            is_admin_query = select(
                exists(GroupMember)
                .where(col(GroupMember.group_id) == space.group_id)
                .where(col(GroupMember.user_id) == self.actor.user_id)
                .where(col(GroupMember.role) == UserRole.admin)
            )
            is_admin = await self.db.scalar(is_admin_query)
            if not is_admin:
                raise UserIsNotGroupAdminError()

        # actor에게 권한이 있는지 검사
        actor_own_query = (
            select(literal(space.space_id), Document.document_id, literal(self.actor.user_id))
            .where(col(Document.document_id).in_(document_ids))
            .where(Document.uploaded_by_user_id == self.actor.user_id)
        )

        actor_own_documents = (await self.db.execute(actor_own_query)).scalars().all()

        # 하나라도 권한이 없는 문서가 있다면 전체 실패
        if len(actor_own_documents) != len(document_ids):
            raise ForbiddenDocumentAccessError()

        stmt = (
            pg_insert(ChatSpaceDocument)
            .from_select(["space_id", "document_id", "added_by_user_id"], actor_own_query)
            .on_conflict_do_nothing(
                index_elements=["space_id", "document_id"]  # 중복 있을 시 무시
            )
            .returning(col(ChatSpaceDocument.document_id))
        )

        result = await self.db.execute(stmt)
        await self.db.commit()

        success_ids = set(result.scalars().all())
        failed_ids = document_ids - success_ids

        return {"success": success_ids, "skipped": failed_ids}


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

        if len(bridge) != len(document_ids):
            raise DocumentNotFoundError()

        # [문제 2] db.delete()는 객체(Instance)를 받아야 하는데, 위에서 Row(튜플)를 받았습니다.
        # 또한 여러 개를 삭제할 때는 루프를 돌거나 객체 리스트를 잘 넘겨야 합니다.

        # [수정 제안]
        # 1. .scalars().all()로 객체 리스트를 받으세요.
        bridges = (await self.db.execute(query)).scalars().all()

        if len(bridges) != len(document_ids):
            raise DocumentNotFoundError()

        # 2. 객체들을 삭제합니다.
        for b in bridges:
            await self.db.delete(b)

        await self.db.commit()


    async def create_chat_session(self, space: ChatSpace, title: str) -> ChatSession:
        """
        챗스페이스에 새 세션을 추가합니다.
        """
        if space.space_id is None:
            raise IllegalStateError()

        new_session = ChatSession(
            space_id=space.space_id, title=title, user_id=self.actor.user_id
        )

        self.db.add(new_session)
        await self.db.commit()
        await self.db.refresh(new_session, attribute_names=["space", "user"])

        return new_session
