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


class Source(BaseModel):
    file_name: str


class ChatRequest(BaseModel):
    query: str
    include_law: Optional[bool] = False
    include_precedent: Optional[bool] = False


class ChatResponse(BaseModel):
    token: Optional[str]
    sources: Optional[list[Source]]