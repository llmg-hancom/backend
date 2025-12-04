from datetime import datetime, timezone
from typing import Annotated, Literal, Self

from fastapi import Depends, Security
from pydantic import PositiveInt
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import joinedload
from sqlmodel import col, delete, exists, literal, select
from sqlmodel.ext.asyncio.session import AsyncSession

from db.session import get_async_db
from errors.document import ForbiddenDocumentAccessError
from errors.general import IllegalStateError
from errors.groups import UserIsNotGroupAdminError, UserIsNotGroupMemberError
from errors.space import ForbiddenSpaceAccessError, SpaceNotFoundError
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

    async def actor_has_space_read_permission(self, space: ChatSpace):
        """
        Actor에게 챗스페이스 읽기 권한이 있는지 검사합니다.
        권한이 없다면 오류가 발생합니다.
        """
        # 개인 챗스페이스이고, actor가 스페이스를 생성한 사람이 아닌 경우
        if (
            space.owner_user_id is not None
            and space.owner_user_id != self.actor.user_id
        ):
            raise ForbiddenSpaceAccessError()

        # 그룹 챗스페이스이고, actor가 그 그룹의 멤버가 아닌 경우
        if space.group_id is not None:
            is_member_query = select(
                exists(GroupMember)
                .where(col(GroupMember.group_id) == space.group_id)
                .where(col(GroupMember.user_id) == self.actor.user_id)
            )
            is_member = await self.db.scalar(is_member_query)

            if not is_member:
                raise ForbiddenSpaceAccessError()

    async def __actor_has_space_write_permission(self, space: ChatSpace):
        """
        Actor에게 챗스페이스 쓰기 권한이 있는지 검사합니다.
        권한이 없다면 이유에 맞는 오류가 발생합니다.
        """
        if self.actor.user_id is None:
            raise IllegalStateError()

        # 개인 챗스페이스이고, actor가 스페이스를 생성한 사람이 아닌 경우
        if (
            space.owner_user_id is not None
            and space.owner_user_id != self.actor.user_id
        ):
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

    async def create_chat_space(self, name: str) -> ChatSpace:
        """
        챗스페이스를 추가합니다.
        """
        if self.actor.user_id is None:
            raise IllegalStateError()

        space = ChatSpace(name=name, owner_user_id=self.actor.user_id)

        self.db.add(space)
        await self.db.flush()
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
        await self.db.flush()
        await self.db.refresh(space)

        return space

    async def get_group_chat_spaces(
        self, group: Group, offset: int, limit: int
    ) -> list[ChatSpace]:
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
        spaces = (await self.db.exec(query)).all()
        return list(spaces)

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

        space = (await self.db.exec(query)).one_or_none()

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
                ChatSpaceDocument,
                col(Document.document_id) == ChatSpaceDocument.document_id,
            )
            .where(ChatSpaceDocument.space_id == space_id)
            .offset(offset)
            .limit(limit)
        )

        # 이제 result는 이미 Document 객체들의 리스트입니다.
        result = (await self.db.exec(query)).all()

        return list(result)

    async def add_document(
        self, space: ChatSpace, document_ids: set[int]
    ) -> dict[Literal["success", "skipped"], set[int]]:
        """
        챗스페이스에 문서를 추가합니다. 개인 챗스페이스일 경우 스페이스를 생성한 사람이,
        그룹 챗스페이스일 경우 스페이스를 소유한 그룹의 admin이 문서를 추가할 수 있습니다.
        """
        # 리스트가 비어있는 경우
        if len(document_ids) == 0:
            return {}

        # 타입 내로잉
        if self.actor.user_id is None:
            raise IllegalStateError()

        if space.space_id is None:
            raise IllegalStateError()

        # Actor에게 챗스페이스 쓰기 권한이 있는지 검사
        await self.__actor_has_space_write_permission(space)

        # actor에게 권한이 있는지 검사
        actor_own_query = (
            select(
                literal(space.space_id),
                Document.document_id,
                literal(self.actor.user_id),
            )
            .where(col(Document.document_id).in_(document_ids))
            .where(Document.uploaded_by_user_id == self.actor.user_id)
        )

        actor_own_documents = (await self.db.exec(actor_own_query)).all()

        # 하나라도 권한이 없는 문서가 있다면 전체 실패
        if len(actor_own_documents) != len(document_ids):
            raise ForbiddenDocumentAccessError()

        stmt = (
            pg_insert(ChatSpaceDocument)
            .from_select(
                ["space_id", "document_id", "added_by_user_id"], actor_own_query
            )
            .on_conflict_do_nothing(
                index_elements=["space_id", "document_id"]  # 중복 있을 시 무시
            )
            .returning(col(ChatSpaceDocument.document_id))
        )

        result = await self.db.exec(stmt)
        await self.db.flush()

        success_ids = set(result.scalars().all())
        skipped_ids = document_ids - success_ids

        return {"success": success_ids, "skipped": skipped_ids}

    async def delete_document(
        self, space: ChatSpace, document_ids: set[int]
    ) -> dict[Literal["success", "skipped"], set[int]]:
        """
        챗스페이스에 연결된 문서를 삭제합니다. 개인 챗스페이스일 경우 스페이스를 생성한 사람이,
        그룹 챗스페이스일 경우 스페이스를 소유한 그룹의 admin이 문서를 삭제할 수 있습니다.
        """
        if space.space_id is None:
            raise IllegalStateError()

        # Actor에게 챗스페이스 쓰기 권한이 있는지 검사
        await self.__actor_has_space_write_permission(space)

        query = (
            delete(ChatSpaceDocument)
            .where(col(ChatSpaceDocument.space_id) == space.space_id)
            .where(col(ChatSpaceDocument.document_id).in_(document_ids))
            .returning(col(ChatSpaceDocument.document_id))
        )

        result = await self.db.exec(query)
        await self.db.flush()

        success_ids = set(result.scalars().all())
        skipped_ids = document_ids - success_ids

        return {"success": success_ids, "skipped": skipped_ids}

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
        await self.db.flush()
        await self.db.refresh(new_session, attribute_names=["space", "user"])

        return new_session

    async def get_chat_sessions(
        self, space: ChatSpace, offset: PositiveInt, limit: PositiveInt
    ) -> list[ChatSession]:
        if self.actor.user_id is None:
            raise IllegalStateError()

        # actor에게 space 읽기 권한이 있는지 확인
        await self.actor_has_space_read_permission(space=space)

        query = (
            select(ChatSession)
            .where(col(ChatSession.space_id) == space.space_id)
            .where(
                col(ChatSession.user_id) == self.actor.user_id
            )  # actor의 ChatSession만 조회
            .where(col(ChatSession.deleted_at).is_(None))  # 삭제되지 않은 경우만 조회
            .offset(offset)
            .limit(limit)
            .options(joinedload(ChatSession.space), joinedload(ChatSession.user))  # type:ignore
        )

        result = await self.db.exec(query)

        return list(result.all())

    async def update_chat_session_title(
        self, title: str, session: ChatSession
    ) -> ChatSession:
        if self.actor.user_id is None:
            raise IllegalStateError()

        # actor의 session인지 확인
        if self.actor.user_id != session.user_id:
            raise

        session.title = title
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        
        return session
