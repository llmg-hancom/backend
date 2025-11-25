from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Security, status

from errors.chat import ForbiddenSpaceAccessError
from errors.general import IllegalStateError
from models import ChatSession, ChatSpace, User
from models.document import DocumentRead
from schemas.chat import (
    ChatSessionCreateRequest,
    ChatSessionRead,
    SpaceCreateRequest,
    SpaceDocumentListRequest,
    SpaceRead,
)
from schemas.pagination import PaginationParams, PaginationResponse
from services.chat_service import ChatService
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
    body: Annotated[SpaceCreateRequest, Body()],
    service: Annotated[ChatService, Depends(ChatService.factory)]
) -> SpaceRead:
    space = await service.create_chat_space(name=body.name)
    return SpaceRead.model_validate(space)


@router.get(
    path="/{space_id}",
    summary="챗스페이스 조회",
    response_model=SpaceRead
)
async def get_space(
    space: Annotated[ChatSpace, Depends(chat_space_from_space_id_path)],
    actor: Annotated[User, Security(get_current_user)]
) -> SpaceRead:
    if actor.user_id != space.owner_user_id:
        raise ForbiddenSpaceAccessError()

    return SpaceRead.model_validate(space)


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
    service: Annotated[ChatService, Depends(ChatService.factory)],
) -> None:
    return await service.delete_chat_space(
        space_id=space_id,
    )


@router.get(
    "/{space_id}/documents",
    summary="챗스페이스에 연결된 문서 목록 조회"
)
async def get_documents_in_chat_space(
    space: Annotated[ChatSpace, Depends(chat_space_from_space_id_path)],
    pagination: Annotated[PaginationParams, Query()],
    service: Annotated[ChatService, Depends(ChatService.factory)],
) -> PaginationResponse[DocumentRead]:
    offset = (pagination.page - 1) * pagination.size
    limit = pagination.size

    if space.space_id is None:
        raise IllegalStateError()

    result =  await service.get_chat_space_documents(
        space_id=space.space_id,
        offset=offset,
        limit=limit,
    )

    return PaginationResponse(
        data=[DocumentRead.model_validate(doc) for doc in result],
        page=pagination.page,
        size=pagination.size
    )


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
        space=space,
        document_ids=body.document_ids
    )


@router.delete(
    "/{space_id}/documents",
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


@router.post(
    "/{space_id}/sessions",
    summary="챗스페이스에 새 세션 생성",
    status_code=status.HTTP_201_CREATED
)
async def create_chat_session(
    space: Annotated[ChatSpace, Depends(chat_space_from_space_id_path)],
    body: Annotated[ChatSessionCreateRequest, Body()],
    service: Annotated[ChatService, Depends(ChatService.factory)],
) -> ChatSessionRead:
    if space.space_id is None:
        raise IllegalStateError()

    result = await service.create_chat_session(
        space=space,
        title=body.title
    )

    return ChatSessionRead.model_validate(result)
