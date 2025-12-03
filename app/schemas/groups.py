from datetime import datetime

from pydantic import BaseModel, EmailStr
from sqlmodel import Field

from models.group import GroupBase
from models.group_member import UserRole
from models.user import UserRead


class GroupCreate(GroupBase):
    pass


class GroupMemberRead(UserRead):
    role: UserRole


class GroupRead(GroupBase):
    group_id: int
    created_at: datetime
    created_by_user: UserRead
    members: list[UserRead]


class GroupReadWithoutMembers(GroupBase):
    group_id: int
    created_at: datetime
    created_by_user: UserRead


class GroupReadWithUserRole(GroupReadWithoutMembers):
    user_role: UserRole


class GroupUserInviteRequest(BaseModel):
    email: EmailStr
    role: UserRole


class GroupUpdate(GroupBase):
    group_name: str = Field(max_length=256, nullable=True, default=None)
    description: str | None = Field(nullable=True, default=None)
