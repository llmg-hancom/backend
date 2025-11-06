from datetime import datetime

from sqlalchemy import Column, TIMESTAMP, func, Text
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from models.user import User
    from models.group_member import GroupMember
    from models.chat_space import ChatSpace


class GroupBase(SQLModel):
    group_name: str = Field(max_length=255, nullable=False)
    description: Optional[str] = Field(sa_column=Column(Text, nullable=False))


class Group(GroupBase, table=True):
    __tablename__ = "groups"
    group_id: Optional[int] = Field(default=None, primary_key=True)
    group_name: str = Field(max_length=255, nullable=False)
    created_by_user_id: int = Field(foreign_key="users.user_id", nullable=False)
    created_at: datetime = Field(
        sa_column=Column(
            TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
        )
    )
    deleted_at: Optional[datetime] = Field(
        default=None, sa_column=Column(TIMESTAMP(timezone=True))
    )

    # Relationships
    created_by_user: "User" = Relationship(back_populates="created_groups")
    members: list["GroupMember"] = Relationship(
        back_populates="group", sa_relationship_kwargs={"cascade": "all, delete"}
    )
    chat_spaces: list["ChatSpace"] = Relationship(
        back_populates="group", sa_relationship_kwargs={"cascade": "all, delete"}
    )