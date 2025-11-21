from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Security, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from db.session import get_async_db
from errors.chat import ForbiddenSpaceAccessError, SpaceNotFoundError
from errors.general import IllegalStateError
from errors.space import NotSpaceAdminError
from models import ChatSpace, User
from schemas.chat import SpaceDocumentListRequest, SpaceRead
from services.chat_service import ChatService
from services.space.add_doc_to_space import add_documents_to_chat_space as doc_service
from utils.auth import get_current_user
from utils.chat import chat_space_from_space_id_path


router = APIRouter(prefix="/spaces")


@router.post(
    path="",
    summary="새 채팅방 생성",
    status_code=status.HTTP_201_CREATED,
    response_model=SpaceRead
)
async def create_space(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Security(get_current_user)],
    name: str,
) -> SpaceRead:
    if current_user.user_id is None:
        raise IllegalStateError()

    new_space = ChatSpace(owner_user_id=current_user.user_id, name=name)
    db.add(new_space)
    await db.flush()
    await db.refresh(new_space)
    return SpaceRead.model_validate(new_space)


@router.delete(
    path="/{space_id}",
    summary="개인 채팅방 삭제",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_204_NO_CONTENT: {
            "description": "채팅방 삭제 성공",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "채팅방이 존재하지 않음",
            "content": {
                "application/json": {
                    "example": {
                        "status_code": 404,
                        "error_code": "SPACE_NOT_FOUND",
                        "message": "채팅방을 찾을 수 없습니다.",
                    }
                }
            },
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "채팅방을 열람할 권한이 없음",
            "content": {
                "application/json": {
                    "example": {
                        "status_code": 403,
                        "error_code": "FORBIDDEN_SPACE_ACCESS",
                        "message": "채팅방에 접근할 권한이 없습니다.",
                    }
                }
            },
        },
    },
)
async def delete_space(
    space_id: Annotated[int, Path(description="채팅방 ID")],
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Security(get_current_user)],
) -> None:
    space = await db.exec(select(ChatSpace).where(ChatSpace.space_id == space_id))
    space_one = space.one_or_none()
    if space_one is None:
        raise SpaceNotFoundError()
    if space_one.owner_user_id != current_user.user_id:
        raise ForbiddenSpaceAccessError()
    space_one.deleted_at = datetime.now(tz=timezone.utc)
    await db.flush()


@router.post(
    "/{space_id}/documents",
    summary="챗 스페이스에 문서 추가",
    status_code=status.HTTP_201_CREATED
)
async def add_documents_to_chat_space(
    space: Annotated[ChatSpace, Depends(chat_space_from_space_id_path)],
    body: Annotated[SpaceDocumentListRequest, Body(description="추가할 문서 ID의 목록")],
    service: Annotated[ChatService, Depends(ChatService.factory)],
) -> None:
    if space.space_id is None:
        raise IllegalStateError()

    return await service.add_document(
        space_id=space.space_id,
        document_ids=body.document_ids
    )


@router.delete(
    "/{space_id}/documents/{document_id}",
    summary="챗스페이스에 연결된 문서 연결 해제",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_documents_to_chat_space(
    space: Annotated[ChatSpace, Depends(chat_space_from_space_id_path)],
    body: Annotated[SpaceDocumentListRequest, Body()],
    service: Annotated[ChatService, Depends(ChatService.factory)],
) -> None:
    if space.space_id is None:
        raise IllegalStateError()

    return await service.delete_document(
        space_id=space.space_id,
        document_ids=body.document_ids
    )
