from datetime import datetime
from typing import Optional, Any, TYPE_CHECKING

from sqlalchemy import Column, Text, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field, Relationship
from pgvector.sqlalchemy import Vector  # pgvector 확장 기능 사용

if TYPE_CHECKING:
    from models.document import Document


class DocumentChunkBase(SQLModel):
    chunk_id: Optional[int] = Field(default=None, primary_key=True)  # SQL의 BIGSERIAL
    document_id: int = Field(foreign_key="documents.document_id", nullable=False)


class DocumentChunk(DocumentChunkBase, table=True):
    """3.1. DocumentChunk (pgvector)"""

    __tablename__ = "document_chunks"

    content: str = Field(sa_column=Column(Text, nullable=False))

    # [핵심] pgvector(1024) 타입
    embedding: Optional[list[float]] = Field(
        default=None, sa_column=Column(Vector(1024))
    )

    # [핵심] 유연한 메타데이터 (JSONB)
    meta: Optional[dict[str, Any]] = Field(
        default_factory=dict, sa_column=Column(JSONB, server_default="{}")
    )

    created_at: datetime = Field(
        sa_column=Column(
            TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
        )
    )

    # Relationship
    document: "Document" = Relationship(back_populates="chunks")