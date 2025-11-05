from typing import Optional, TYPE_CHECKING

from sqlmodel import SQLModel, Field, Relationship, ForeignKey
from sqlalchemy import Column, TIMESTAMP, func
from datetime import datetime

if TYPE_CHECKING:
    from models.chat_space import ChatSpace
    from models.user import User
    from models.chat_message import ChatMessage


class ChatSessionBase(SQLModel):
    title: str = Field(max_length=255, nullable=False)


class ChatSession(ChatSessionBase, table=True):
    """3.4. ChatSessions (채팅 세션/스레드)"""

    __tablename__ = "chat_sessions"

    session_id: Optional[int] = Field(default=None, primary_key=True)
    space_id: int = Field(
        foreign_key="chat_spaces.space_id", nullable=False, index=True
    )
    user_id: Optional[int] = Field(
        default=None, sa_column_args=[ForeignKey("users.user_id", ondelete="SET NULL")]
    )

    created_at: datetime = Field(
        sa_column=Column(
            TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
        ),
    )

    # [핵심] ON UPDATE 트리거 구현
    updated_at: datetime = Field(
        sa_column=Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        ),
    )

    deleted_at: Optional[datetime] = Field(
        default=None, sa_column=Column(TIMESTAMP(timezone=True))
    )

    # Relationships
    space: "ChatSpace" = Relationship(back_populates="sessions")
    user: Optional["User"] = Relationship(back_populates="chat_sessions")
    messages: list["ChatMessage"] = Relationship(
        back_populates="session", sa_relationship_kwargs={"cascade": "all, delete"}
    )