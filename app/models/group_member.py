from datetime import datetime
from enum import Enum
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Column, TIMESTAMP, func
from sqlmodel import SQLModel, Field, Relationship, UniqueConstraint, Enum as SaEnum

if TYPE_CHECKING:
    from models.user import User
    from models.group import Group


class UserRole(str, Enum):
    admin = "admin"
    member = "member"


class GroupMemberBase(SQLModel):
    group_member_id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.user_id", nullable=False)
    group_id: int = Field(foreign_key="groups.group_id", nullable=False)


class GroupMember(GroupMemberBase, table=True):
    """2.2. GroupMembers (그룹 멤버)"""

    __tablename__ = "group_members"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "group_id", name="group_members_user_id_group_id_key"
        ),
    )
    role: UserRole = Field(
        default=UserRole.member, sa_column=Column(SaEnum(UserRole), nullable=False)
    )
    joined_at: datetime = Field(
        sa_column=Column(
            TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
        )
    )

    # Relationships
    user: "User" = Relationship(back_populates="group_memberships")
    group: "Group" = Relationship(back_populates="members")
