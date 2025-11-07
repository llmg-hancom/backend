from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Session, SQLModel, create_engine, text

from core.config import settings
from models.chat_message import ChatMessage  # noqa: F401
from models.chat_session import ChatSession  # noqa: F401
from models.chat_space import ChatSpace  # noqa: F401
from models.chat_space_document import ChatSpaceDocument  # noqa: F401
from models.document import Document  # noqa: F401
from models.document_chunk import DocumentChunk  # noqa: F401
from models.group import Group  # noqa: F401
from models.group_member import GroupMember  # noqa: F401
from models.refresh_token import RefreshToken  # noqa: F401
from models.social_account import SocialAccount  # noqa: F401
from models.user import User  # noqa: F401


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
