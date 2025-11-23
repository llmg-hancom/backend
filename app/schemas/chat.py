from typing import Annotated

from pydantic import BaseModel, Field

from models.chat_space import ChatSpaceBase


class SpaceCreateRequest(ChatSpaceBase):
    pass


class SpaceRead(ChatSpaceBase):
    space_id: int
    owner_user_id: int | None
    group_id: int | None


class AllSpacesRead(BaseModel):
    spaces: list[SpaceRead]


class Source(BaseModel):
    file_name: str


class ChatRequest(BaseModel):
    query: str
    include_law: bool = False
    include_precedent: bool = False


class ChatResponse(BaseModel):
    token: str | None
    sources: list[Source] | None


class SpaceDocumentListRequest(BaseModel):
    document_ids: set[Annotated[int, Field(gt=0, description="추가할 문서 ID")]] = (
        Field(description="추가할 문서 목록", default_factory=set)
    )
