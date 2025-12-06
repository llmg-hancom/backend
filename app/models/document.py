from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import TIMESTAMP, Column, func, Index
from sqlalchemy import Enum as SaEnum
from sqlmodel import Field, Relationship, SQLModel


if TYPE_CHECKING:
    from models.chat_space_document import ChatSpaceDocument
    from models.document_chunk import DocumentChunk
    from models.user import User


class DocumentStatus(StrEnum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    error = "error"


class DocumentScope(StrEnum):
    private = "private"
    public_law = "public_law"
    precedent = "precedent"


class DocumentBase(SQLModel):
    document_id: int | None = Field(default=None, primary_key=True)
    file_name: str = Field(max_length=255, nullable=False)
    status: DocumentStatus = Field(
        default=DocumentStatus.pending,
        sa_column=Column(
            SaEnum(DocumentStatus),
            server_default=DocumentStatus.pending,
            index=True,
            nullable=False,
        ),
    )


class Document(DocumentBase, table=True):
    """2.3. Documents (문서 메타데이터)"""

    __tablename__ = "documents"
    file_path: str | None = Field(default=None, max_length=1024, unique=True)
    uploaded_by_user_id: int = Field(
        foreign_key="users.user_id", nullable=False, index=True
    )
    file_hash: str | None = Field(default=None, max_length=64, unique=True)
    document_scope: DocumentScope = Field(
        default=DocumentScope.private,
        sa_column=Column(
            SaEnum(DocumentScope),
            server_default=DocumentScope.private,
            index=True,
            nullable=False,
        ),
    )
    created_at: datetime = Field(
        sa_column=Column(
            TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
        )
    )
    deleted_at: datetime | None = Field(
        default=None, sa_column=Column(TIMESTAMP(timezone=True))
    )

    # Relationships
    uploaded_by_user: "User" = Relationship(back_populates="uploaded_documents")
    chunks: list["DocumentChunk"] = Relationship(
        back_populates="document", cascade_delete=True
    )
    chat_space_links: list["ChatSpaceDocument"] = Relationship(
        back_populates="document", cascade_delete=True
    )

    __table_args__ = (
        Index(
            "ix_documents_deleted_at",
            "deleted_at",
            postgresql_where=Column("deleted_at").is_not(None),
        ),
    )


class DocumentRead(DocumentBase):
    document_id: int
    file_path: str | None
    uploaded_by_user_id: int
    status: DocumentStatus
    created_at: datetime
