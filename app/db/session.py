from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import create_engine, SQLModel, Session, text
from core.config import settings

# models
from models.user import User, RefreshToken
from models.document import Document
from models.document_chunk import DocumentChunk
from models.social_account import SocialAccount
from models.group import Group
from models.group_member import GroupMember
from models.chat_space import ChatSpace
from models.chat_session import ChatSession
from models.chat_space_document import ChatSpaceDocument
from models.chat_message import ChatMessage


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
