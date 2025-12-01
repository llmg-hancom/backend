from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from models.chat_message import ChatMessageBase
from models.chat_session import ChatSessionBase
from models.chat_space import ChatSpaceBase
from models.user import UserRead


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


class ChatSessionRead(ChatSessionBase):
    session_id: int
    created_at: datetime
    updated_at: datetime
    space: SpaceRead
    user: UserRead


class ChatSessionCreateRequest(ChatSessionBase):
    pass


class ChatSessionUpdateRequest(ChatSessionBase):
    pass


class ChatMessageRead(ChatMessageBase):
    """채팅 메시지 응답 스키마"""

    message_id: int
    created_at: datetime
    sources: dict | None = None
