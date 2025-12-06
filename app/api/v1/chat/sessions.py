from typing import Annotated

from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.orm import joinedload
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from db.session import get_async_db
from errors.chat import ChatSessionNotFoundError, ForbiddenChatSessionAccessError
from models import GroupMember
from models.chat_message import ChatMessage
from models.chat_session import ChatSession
from models.user import User
from schemas.chat import ChatMessageRead, ChatSessionRead, ChatSessionUpdateRequest
from schemas.pagination import PaginationParams, PaginationResponse
from services.chat_service import ChatService
from services.chat_session import ChatSessionService
from utils.auth import get_current_user
from utils.chat import chat_session_from_session_id_path
from utils.openapi import generate_openapi_error_response as error_docs


router = APIRouter(prefix="/sessions")


@router.get(
    path="/{session_id}/messages",
    summary="세션의 대화 기록 조회 (페이지네이션)",
    response_model=PaginationResponse[ChatMessageRead],
)
async def get_chat_session_history(
    session_id: int,
    params: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """
    특정 채팅 세션의 모든 대화 기록을 페이지네이션하여 조회합니다.
    최신 메시지가 먼저 반환됩니다.

    - **session_id**: 대화 기록을 조회할 채팅 세션의 ID
    - **page**: 페이지 번호 (1부터 시작)
    - **size**: 페이지 당 메시지 수
    """
    # 1. 세션 존재 여부 및 권한 확인
    statement = (
        select(ChatSession)
        .where(ChatSession.session_id == session_id)
        .options(joinedload(ChatSession.space)) # type: ignore
    )
    result = await db.exec(statement)
    chat_session = result.one_or_none()

    if not chat_session:
        raise ChatSessionNotFoundError(session_id)

    is_owner = chat_session.space.owner_user_id == current_user.user_id
    if chat_session.space.group_id is not None:
        gm_query = (
            select(GroupMember)
            .where(GroupMember.user_id == current_user.user_id)
            .where(GroupMember.group_id == chat_session.space.group_id)
        )
        is_group_member = (await db.exec(gm_query)).first() is not None
    else:
        is_group_member = False

    if not (is_owner or is_group_member):
        raise ForbiddenChatSessionAccessError()

    # 2. 전체 메시지 수 조회
    total_count_stmt = select(func.count(ChatMessage.message_id)).where(
        ChatMessage.session_id == session_id
    )
    total_count_result = await db.exec(total_count_stmt)
    total = total_count_result.one()

    # 3. 해당 페이지의 메시지 목록 조회 (최신순으로)
    offset = (params.page - 1) * params.size
    messages_stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(
            col(ChatMessage.created_at).desc(),
            col(ChatMessage.message_id).desc(),  # 2차 정렬 기준 추가
        )
        .offset(offset)
        .limit(params.size)
    )
    messages_result = await db.exec(messages_stmt)
    messages = messages_result.all()

    # 4. 페이지네이션 응답 모델로 반환
    return PaginationResponse(
        page=params.page,
        size=params.size,
        data=list(messages),
    )


@router.patch("/{session_id}", summary="채팅 세션 제목 변경")
async def change_session_info(
    session: Annotated[ChatSession, Depends(chat_session_from_session_id_path)],
    body: Annotated[ChatSessionUpdateRequest, Body()],
    service: Annotated[ChatService, Depends(ChatService.factory)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> ChatSessionRead:
    result = await service.update_chat_session_title(title=body.title, session=session)
    await db.refresh(result,attribute_names=["user","space"])

    return ChatSessionRead.model_validate(result)


@router.delete(
    "/{session_id}",
    summary="채팅 세션 삭제",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        **error_docs(ChatSessionNotFoundError(1), ForbiddenChatSessionAccessError())
    },
)
async def delete_session(
    session: Annotated[ChatSession, Depends(chat_session_from_session_id_path)],
    service: Annotated[ChatSessionService, Depends(ChatSessionService.factory)],
) -> None:
    await service.delete_chat_session(
        session=session
    )
