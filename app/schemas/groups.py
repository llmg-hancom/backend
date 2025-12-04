from datetime import datetime

from pydantic import BaseModel, EmailStr
from sqlmodel import Field

from models.group import GroupBase
from models.group_member import GroupMemberBase, UserRole
from models.user import UserRead


class GroupCreate(GroupBase):
    pass


class GroupMemberRead(GroupMemberBase):
    """그룹 멤버 정보와 역할을 함께 반환하는 스키마"""

    user: UserRead  # 사용자의 상세 정보


class GroupRead(GroupBase):
    """멤버 목록을 포함한 그룹 상세 정보 스키마"""

    group_id: int
    created_at: datetime
    created_by_user: UserRead
    members: list[GroupMemberRead]  # GroupMemberRead 리스트로 변경


class GroupReadWithoutMembers(GroupBase):
    group_id: int
    created_at: datetime
    created_by_user: UserRead


class GroupReadWithMyRole(GroupReadWithoutMembers):
    user_role: UserRole


class GroupUserInviteRequest(BaseModel):
    email: EmailStr
    role: UserRole


class GroupUpdate(GroupBase):
    group_name: str | None = Field(max_length=256, default=None)
    description: str | None = Field(default=None)
