from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime, timezone
import uuid


class ChatSpaceBase(SQLModel):
    name: str = Field()


class ChatSpace(ChatSpaceBase, table=True):
    __tablename__ = "chat_space"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID | None = Field(foreign_key="user.id", ondelete="SET NULL")
    group_id: uuid.UUID = Field(foreign_key="group.id", ondelete="CASCADE")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
