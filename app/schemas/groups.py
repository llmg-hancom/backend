from datetime import datetime

from models.group import GroupBase
from models.user import UserRead


class GroupCreate(GroupBase):
    pass

class GroupRead(GroupBase):
    group_id: int

    created_at: datetime

    created_by_user: UserRead

    members: list[UserRead]
