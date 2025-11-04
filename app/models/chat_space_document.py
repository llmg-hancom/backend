from sqlmodel import SQLModel, Field, Relationship, UniqueConstraint
from sqlalchemy import Column, DateTime
from datetime import datetime, timezone
import uuid


class ChatSpaceDocumentBase(SQLModel):
    space_id: uuid.UUID = Field(foreign_key="chat_space.id")
    document_id: uuid.UUID = Field(foreign_key="document.id")

    __table_args__ = (UniqueConstraint("space_id", "document_id"),)


class ChatSpaceDocument(ChatSpaceDocumentBase, table=True):
    __tablename__ = "chat_space_document"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    added_user: uuid.UUID = Field(foreign_key="user.id", ondelete="CASCADE")
    added_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
