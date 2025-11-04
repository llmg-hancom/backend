from sqlmodel import create_engine, SQLModel, Session
from os import environ as env

# models
from models.user import User
from models.document import Document
from models.social_account import SocialAccount
from models.group import Group
from models.group_member import GroupMember
from models.chat_space import ChatSpace
from models.chat_session import ChatSession
from models.chat_space_document import ChatSpaceDocument


DB_USER = env.get("POSTGRES_USER")
DB_PASSWORD = env.get("POSTGRES_PASSWORD")
DB_HOST = env.get("POSTGRES_HOST")
DB_PORT = env.get("POSTGRES_PORT")
DB_NAME = env.get("POSTGRES_NAME")

db_url = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(db_url, echo=True)
SQLModel.metadata.create_all(engine)


def get_db():
    with Session(engine) as session:
        yield session
