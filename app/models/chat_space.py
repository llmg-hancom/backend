from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import TIMESTAMP, CheckConstraint, Column, func
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from models.chat_session import ChatSession
    from models.chat_space_document import ChatSpaceDocument
    from models.group import Group
    from models.user import User


class ChatSpaceBase(SQLModel):
    name: str = Field(max_length=255, nullable=False)


class ChatSpace(ChatSpaceBase, table=True):
    """3.2. ChatSpaces (채팅 공간)"""

    __tablename__ = "chat_spaces"
    __table_args__ = (
        CheckConstraint(
            "(owner_user_id IS NOT NULL AND group_id IS NULL) OR (owner_user_id IS NULL AND group_id IS NOT NULL)",
            name="chk_space_owner",
        ),
    )
    space_id: Optional[int] = Field(default=None, primary_key=True)

    owner_user_id: Optional[int] = Field(default=None, foreign_key="users.user_id")
    group_id: Optional[int] = Field(default=None, foreign_key="groups.group_id")
    created_at: datetime = Field(
        sa_column=Column(
            TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
        )
    )
    deleted_at: Optional[datetime] = Field(
        default=None, sa_column=Column(TIMESTAMP(timezone=True))
    )

    # Relationships
    owner_user: Optional["User"] = Relationship(back_populates="owned_chat_spaces")
    group: Optional["Group"] = Relationship(back_populates="chat_spaces")
    documents: list["ChatSpaceDocument"] = Relationship(
        back_populates="space", sa_relationship_kwargs={"cascade": "all, delete"}
    )
    sessions: list["ChatSession"] = Relationship(
        back_populates="space", sa_relationship_kwargs={"cascade": "all, delete"}
    )