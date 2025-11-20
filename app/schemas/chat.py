from typing import Optional

from pydantic import BaseModel

from models.chat_space import ChatSpaceBase


class SpaceCreateRequest(ChatSpaceBase):
    pass


class SpaceRead(ChatSpaceBase):
    space_id: int
    owner_user_id: Optional[int]
    group_id: Optional[int]


class AllSpacesRead(BaseModel):
    spaces: list[SpaceRead]

