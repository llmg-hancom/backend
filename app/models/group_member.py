from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import TIMESTAMP, Column, func
from sqlmodel import Enum as SaEnum
from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint


if TYPE_CHECKING:
    from models.group import Group
    from models.user import User


class UserRole(str, Enum):
    admin = "admin"
    member = "member"


class GroupMemberBase(SQLModel):
    role: UserRole = Field(
        default=UserRole.member, sa_column=Column(SaEnum(UserRole), nullable=False)
    )
    joined_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        sa_column=Column(
            TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
        ),
    )


class GroupMember(GroupMemberBase, table=True):
    """2.2. GroupMembers (그룹 멤버)"""

    __tablename__ = "group_members"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "group_id", name="group_members_user_id_group_id_key"
        ),
    )
    group_member_id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.user_id", nullable=False)
    group_id: int = Field(foreign_key="groups.group_id", nullable=False)

    # Relationships
    user: "User" = Relationship(back_populates="group_memberships")
    group: "Group" = Relationship(back_populates="members")
