from typing import Optional, Any, TYPE_CHECKING

from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, Text, TIMESTAMP, func, Enum as SaEnum
from datetime import datetime
from enum import Enum

if TYPE_CHECKING:
    from models.chat_session import ChatSession


class ChatRole(str, Enum):
    user = "user"
    ai = "ai"


class ChatMessageBase(SQLModel):
    role: ChatRole = Field()
    message: str = Field()


class ChatMessage(ChatMessageBase, table=True):
    """3.5. ChatMessages (개별 메시지)"""

    __tablename__ = "chat_messages"

    message_id: Optional[int] = Field(default=None, primary_key=True)  # SQL의 BIGSERIAL
    session_id: int = Field(
        foreign_key="chat_sessions.session_id", nullable=False, index=True
    )
    role: ChatRole = Field(sa_column=Column(SaEnum(ChatRole), nullable=False))
    content: str = Field(sa_column=Column(Text, nullable=False))

    # [RAG 핵심] 답변의 근거가 된 출처 (JSONB)
    sources: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))

    created_at: datetime = Field(
        sa_column=Column(
            TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
        )
    )

    # Relationship
    session: "ChatSession" = Relationship(back_populates="messages")