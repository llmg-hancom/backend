from datetime import datetime
from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector  # pgvector 확장 기능 사용
from sqlalchemy import TIMESTAMP, Column, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel, Index, text


if TYPE_CHECKING:
    from models.document import Document


class DocumentChunkBase(SQLModel):
    chunk_id: int | None = Field(default=None, primary_key=True)  # SQL의 BIGSERIAL
    document_id: int = Field(
        foreign_key="documents.document_id", nullable=False, index=True
    )


class DocumentChunk(DocumentChunkBase, table=True):
    """3.1. DocumentChunk (pgvector)"""

    __tablename__ = "document_chunks"

    content: str = Field(sa_column=Column(Text, nullable=False))

    # [핵심] pgvector(1024) 타입
    embedding: Any = Field(default=None, sa_column=Column(Vector(1024)))

    # [핵심] 유연한 메타데이터 (JSONB)
    meta: dict[str, Any] | None = Field(
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
            "ix_law_category",
            text("(meta ->> '법령명')"),
            postgresql_where=text("(meta ->> '법령명') IS NOT NULL"),
        ),
        Index(
            "ix_law_jo_number",
            text("(substring(meta ->> '조' from '제([0-9]+)조')::int)"),
            # 데이터가 더러워서 추출이 안 되는 경우 에러 방지용 (부분 인덱스)
            postgresql_where=text(
                "((meta ->> '조') IS NOT NULL) AND (meta ->> '조' ~ '^제[0-9]+조')"
            ),
        ),
        Index(
            "ix_precedent_case_number",
            text("(meta ->> '사건번호')"),
            postgresql_where=text("(meta ->> '사건번호') IS NOT NULL"),
        ),
        Index(
            "ix_precedent_decision_date",
            text("(meta ->> '선고일자')"),
            postgresql_where=text("(meta ->> '선고일자') IS NOT NULL"),
        ),
    )
