from core.config import settings

# models
from sqlmodel import Session, SQLModel, create_engine, text

# settings에서 database_url 프로퍼티 사용
engine = create_engine(settings.database_url, echo=True)
with Session(engine) as session:
    session.exec(text("CREATE EXTENSION IF NOT EXISTS vector;"))
    session.commit()
SQLModel.metadata.create_all(engine)

with Session(engine) as session:
    # 테이블 생성 (SQLModel.metadata.create_all(engine)) 이후
    session.exec(
        text("""
        CREATE INDEX IF NOT EXISTS hnsw_embedding_idx
        ON document_chunks
        USING hnsw (embedding vector_l2_ops)
        WITH (m = 16, ef_construction = 64);
    """)
    )
    session.commit()


def get_db():
    with Session(engine) as session:
        yield session
