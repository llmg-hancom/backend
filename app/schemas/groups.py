from datetime import datetime

from pydantic import BaseModel, EmailStr

from models.group import GroupBase
from models.group_member import UserRole
from models.user import UserRead


class GroupCreate(GroupBase):
    pass

class GroupRead(GroupBase):
    group_id: int

    created_at: datetime

    created_by_user: UserRead

    members: list[UserRead]


class GroupUserInviteRequest(BaseModel):
    email: EmailStr

    role: UserRole
