from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import TIMESTAMP, CheckConstraint, Column, func, Index
from sqlmodel import Field, Relationship, SQLModel


if TYPE_CHECKING:
    from models.chat_session import ChatSession
    from models.chat_space_document import ChatSpaceDocument
    from models.group import Group
    from models.user import User


class ChatSpaceBase(SQLModel):
    name: str = Field(max_length=255, nullable=False)


class ChatSpace(ChatSpaceBase, table=True):
    """3.2. ChatSpaces (채팅 공간)"""

    __tablename__ = "chat_spaces"

    space_id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int | None = Field(
        default=None, foreign_key="users.user_id", ondelete="CASCADE"
    )
    group_id: int | None = Field(
        default=None, foreign_key="groups.group_id", ondelete="CASCADE"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        sa_column=Column(
            TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
        ),
    )
    deleted_at: datetime | None = Field(
        default=None, sa_column=Column(TIMESTAMP(timezone=True))
    )

    # Relationships
    owner_user: Optional["User"] = Relationship(back_populates="owned_chat_spaces")
    group: Optional["Group"] = Relationship(back_populates="chat_spaces")
    documents: list["ChatSpaceDocument"] = Relationship(
        back_populates="space", cascade_delete=True
    )
    sessions: list["ChatSession"] = Relationship(
        back_populates="space", cascade_delete=True
    )
    __table_args__ = (
        CheckConstraint(
            "(owner_user_id IS NOT NULL AND group_id IS NULL) OR (owner_user_id IS NULL AND group_id IS NOT NULL)",
            name="chk_space_owner",
        ),
        # owner_user_id가 NULL이 아닌 행만 인덱싱
        Index(
            "ix_chat_spaces_owner_user_id",
            "owner_user_id",
            postgresql_where=Column("owner_user_id").is_not(None),
        ),
        # group_id가 NULL이 아닌 행만 인덱싱
        Index(
            "ix_chat_spaces_group_id",
            "group_id",
            postgresql_where=Column("group_id").is_not(None),
        ),
        Index(
            "ix_chat_spaces_deleted_at",
            "deleted_at",
            postgresql_where=Column("deleted_at").is_not(None),
        ),
    )
