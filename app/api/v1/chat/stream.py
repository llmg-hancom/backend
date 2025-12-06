from typing import Annotated

from fastapi import APIRouter, Depends, Path, Security
from fastapi.responses import StreamingResponse
from rag.agent import event_generator
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from db.session import get_async_db
from errors.chat import ChatSessionNotFoundError, ForbiddenChatSessionAccessError
from models import ChatSession, User
from schemas.chat import ChatRequest
from utils.auth import get_current_user


router = APIRouter(prefix="/sessions")


@router.post("/{session_id}/stream")
async def stream_session(
    session_id: Annotated[int, Path(description="채팅 세션 ID")],
    current_user: Annotated[User, Security(get_current_user)],
    request: ChatRequest,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> StreamingResponse:
    session = await db.exec(
        select(ChatSession).where(ChatSession.session_id == session_id)
    )
    current_session = session.one_or_none()
    if current_session is None:
        raise ChatSessionNotFoundError(session_id)
    if current_session.user_id != current_user.user_id:
        raise ForbiddenChatSessionAccessError()

    return StreamingResponse(
        event_generator(current_session, request), media_type="text/event-stream"
    )


    
