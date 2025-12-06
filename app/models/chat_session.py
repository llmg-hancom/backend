from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import TIMESTAMP, Column, func, Index
from sqlmodel import Field, ForeignKey, Relationship, SQLModel


if TYPE_CHECKING:
    from models.chat_message import ChatMessage
    from models.chat_space import ChatSpace
    from models.user import User


class ChatSessionBase(SQLModel):
    title: str = Field(max_length=255, nullable=False)


class ChatSession(ChatSessionBase, table=True):
    """3.4. ChatSessions (채팅 세션/스레드)"""

    __tablename__ = "chat_sessions"

    session_id: int | None = Field(default=None, primary_key=True)
    space_id: int = Field(
        foreign_key="chat_spaces.space_id", nullable=False, index=True
    )
    user_id: int | None = Field(
        default=None, sa_column_args=[ForeignKey("users.user_id", ondelete="SET NULL")]
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
        ),
    )

    # [핵심] ON UPDATE 트리거 구현
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        ),
    )

    deleted_at: datetime | None = Field(
        default=None, sa_column=Column(TIMESTAMP(timezone=True))
    )

    # Relationships
    space: "ChatSpace" = Relationship(back_populates="sessions")
    user: Optional["User"] = Relationship(back_populates="chat_sessions")
    messages: list["ChatMessage"] = Relationship(
        back_populates="session", cascade_delete=True
    )
    __table_args__ = (
        Index(
            "ix_chat_sessions_deleted_at",
            "deleted_at",
            postgresql_where=Column("deleted_at").is_not(None),
        ),
    )
