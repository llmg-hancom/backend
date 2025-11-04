from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime
from datetime import datetime, timezone
import uuid


class ChatSessionBase(SQLModel):
    title: str = Field()


class ChatSession(ChatSessionBase, table=True):
    __tablename__ = "chat_session"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", ondelete="CASCADE")
    space_id: uuid.UUID = Field(foreign_key="chat_space.id", ondelete="CASCADE")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
