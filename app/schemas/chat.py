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


class SpaceDocumentListRequest(BaseModel):
    document_ids: set[Annotated[int, Field(gt=0, description="추가할 문서 ID")]] \
        = Field(description="추가할 문서 목록", default_factory=set)
