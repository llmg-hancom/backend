from sqlmodel import SQLModel, Field
from datetime import datetime, timezone
from uuid import UUID, uuid4
from enum import Enum


class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"


class DocumentBase(SQLModel):
    file_name: str = Field()


class Document(DocumentBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    file_path: str = Field()
    owner: UUID = Field(foreign_key="user.id", ondelete="CASCADE")
    status: DocumentStatus = Field(default=DocumentStatus.PENDING)
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))


class DocumentRead(DocumentBase):
    id: UUID
    file_path: str
    owner: UUID
    status: DocumentStatus
    created_at: datetime
