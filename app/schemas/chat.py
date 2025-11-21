from typing import Annotated, Optional

from pydantic import BaseModel, Field

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

class SpaceDocumentListRequest(BaseModel):
    document_ids: set[Annotated[int, Field(gt=0, description="추가할 문서 ID")]] \
        = Field(description="추가할 문서 목록", default_factory=set)
