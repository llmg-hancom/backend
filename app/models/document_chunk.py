from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from pgvector.sqlalchemy import Vector  # pgvector 확장 기능 사용
from sqlalchemy import TIMESTAMP, Column, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel, Index, text


if TYPE_CHECKING:
    from models.document import Document


class DocumentChunkBase(SQLModel):
    chunk_id: Optional[int] = Field(default=None, primary_key=True)  # SQL의 BIGSERIAL
    document_id: int = Field(
        foreign_key="documents.document_id", nullable=False, index=True
    )


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
    __table_args__ = (
        Index(
            "hnsw_embedding_idx",  # 1. 인덱스 이름
            "embedding",  # 2. 적용할 컬럼 이름
            # 3. USING hnsw
            postgresql_using="hnsw",
            # 4. WITH (m = 16, ef_construction = 64)
            postgresql_with={"m": 16, "ef_construction": 64},
            # 5. (embedding vector_cosine_ops)
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index(
            "ix_precedent_case_number",
            text("((meta ->> '사건번호'))"),
            postgresql_where=text("(meta ->> '사건번호') IS NOT NULL"),
        ),
        Index(
            "ix_precedent_decision_date",
            text("((meta ->> '선고일자'))"),
            postgresql_where=text("(meta ->> '선고일자') IS NOT NULL"),
        ),
    )
