from typing import Optional, TYPE_CHECKING

from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, TIMESTAMP, func, Enum as SaEnum
from datetime import datetime
from enum import Enum

if TYPE_CHECKING:
    from models.user import User
    from models.chat_space_document import ChatSpaceDocument
    from models.document_chunk import DocumentChunk


class DocumentStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    error = "error"


class DocumentScope(str, Enum):
    private = "private"
    public_law = "public_law"


class DocumentBase(SQLModel):
    file_name: str = Field(max_length=255, nullable=False)


class Document(DocumentBase, table=True):
    """2.3. Documents (문서 메타데이터)"""

    __tablename__ = "documents"
    document_id: Optional[int] = Field(default=None, primary_key=True)
    file_path: Optional[str] = Field(
        default=None, max_length=1024, sa_column_kwargs={"unique": True}
    )
    uploaded_by_user_id: int = Field(foreign_key="users.user_id", nullable=False)
    file_hash: Optional[str] = Field(
        default=None, max_length=64, sa_column_kwargs={"unique": True}
    )
    document_scope: DocumentScope = Field(
        default=DocumentScope.private,
        sa_column=Column(SaEnum(DocumentScope), nullable=False),
    )
    status: DocumentStatus = Field(
        default=DocumentStatus.pending,
        sa_column=Column(SaEnum(DocumentStatus), index=True, nullable=False),
    )
    created_at: datetime = Field(
        sa_column=Column(
            TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
        )
    )
    deleted_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(TIMESTAMP(timezone=True), index=True),
    )

    # Relationships
    uploaded_by_user: "User" = Relationship(back_populates="uploaded_documents")
    chunks: list["DocumentChunk"] = Relationship(
        back_populates="document", sa_relationship_kwargs={"cascade": "all, delete"}
    )
    chat_space_links: list["ChatSpaceDocument"] = Relationship(
        back_populates="document", sa_relationship_kwargs={"cascade": "all, delete"}
    )


class DocumentRead(DocumentBase):
    document_id: int
    file_path: Optional[str]
    uploaded_by_user_id: int
    status: DocumentStatus
    created_at: datetime
