from sqlmodel import create_engine, SQLModel, Session
from core.config import settings

# models
from models.user import User
from models.document import Document
from models.social_account import SocialAccount
from models.group import Group
from models.group_member import GroupMember
from models.chat_space import ChatSpace
from models.chat_session import ChatSession
from models.chat_space_document import ChatSpaceDocument


# settings에서 database_url 프로퍼티 사용
engine = create_engine(settings.database_url, echo=True)
SQLModel.metadata.create_all(engine)


def get_db():
    with Session(engine) as session:
        yield session
