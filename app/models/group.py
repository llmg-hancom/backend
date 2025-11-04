from sqlmodel import SQLModel, Field, Relationship
from .user import User
import uuid


class GroupBase(SQLModel):
    name: str = Field()
    description: str | None = Field(default=None)


class Group(GroupBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    create_user_id: uuid.UUID | None = Field(foreign_key="user.id", ondelete="SET NULL")
