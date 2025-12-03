from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Security, status
from pydantic import PositiveInt

from errors.chat import ForbiddenSpaceAccessError
from errors.general import IllegalStateError
from models import ChatSpace, User
from models.document import DocumentRead
from schemas.bulk import BulkJobResponse
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
    response_model=SpaceRead,
)
async def create_space(
    body: Annotated[SpaceCreateRequest, Body()],
    service: Annotated[ChatService, Depends(ChatService.factory)],
) -> SpaceRead:
    space = await service.create_chat_space(name=body.name)
    return SpaceRead.model_validate(space)


@router.get(path="/{space_id}", summary="챗스페이스 조회", response_model=SpaceRead)
async def get_space(
    space: Annotated[ChatSpace, Depends(chat_space_from_space_id_path)],
    actor: Annotated[User, Security(get_current_user)],
) -> SpaceRead:
    if actor.user_id != space.owner_user_id:
        raise ForbiddenSpaceAccessError()

    return space


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


@router.get("/{space_id}/documents", summary="챗스페이스에 연결된 문서 목록 조회")
async def get_documents_in_chat_space(
    space: Annotated[ChatSpace, Depends(chat_space_from_space_id_path)],
    pagination: Annotated[PaginationParams, Query()],
    service: Annotated[ChatService, Depends(ChatService.factory)],
) -> PaginationResponse[DocumentRead]:
    offset = (pagination.page - 1) * pagination.size
    limit = pagination.size

    if space.space_id is None:
        raise IllegalStateError()

    result = await service.get_chat_space_documents(
        space_id=space.space_id,
        offset=offset,
        limit=limit,
    )

    return PaginationResponse(data=result, page=pagination.page, size=pagination.size)


@router.post(
    "/{space_id}/documents",
    summary="챗 스페이스에 문서 추가",
    status_code=status.HTTP_201_CREATED,
)
async def add_documents_to_chat_space(
    space: Annotated[ChatSpace, Depends(chat_space_from_space_id_path)],
    body: Annotated[
        SpaceDocumentListRequest, Body(description="추가할 문서 ID의 목록")
    ],
    service: Annotated[ChatService, Depends(ChatService.factory)],
) -> BulkJobResponse[PositiveInt]:
    """
    챗스페이스에 여러 개의 문서를 추가합니다.
    만약 추가하려는 문서 중 사용자의 문서가 아닌 것이 있으면 오류를 반환합니다.
    성공 응답에는 성공/스킵한 문서 ID가 반환됩니다.
    """
    if space.space_id is None:
        raise IllegalStateError()

    result = await service.add_document(space=space, document_ids=body.document_ids)

    return BulkJobResponse[PositiveInt].model_validate(result)


@router.delete(
    "/{space_id}/documents",
    summary="챗스페이스에 연결된 문서 연결 해제",
    status_code=status.HTTP_200_OK,
)
async def delete_documents_to_chat_space(
    space: Annotated[ChatSpace, Depends(chat_space_from_space_id_path)],
    body: Annotated[SpaceDocumentListRequest, Body()],
    service: Annotated[ChatService, Depends(ChatService.factory)],
) -> BulkJobResponse[PositiveInt]:
    """
    챗스페이스에 추가된 문서 여러 개를 제거합니다.
    삭제 시점에 문서가 존재하지 않는다면 건너뜁니다.
    """
    if space.space_id is None:
        raise IllegalStateError()

    result = await service.delete_document(space=space, document_ids=body.document_ids)

    return BulkJobResponse[PositiveInt].model_validate(result)


@router.post(
    "/{space_id}/sessions",
    summary="챗스페이스에 새 세션 생성",
    status_code=status.HTTP_201_CREATED,
)
async def create_chat_session(
    space: Annotated[ChatSpace, Depends(chat_space_from_space_id_path)],
    body: Annotated[ChatSessionCreateRequest, Body()],
    service: Annotated[ChatService, Depends(ChatService.factory)],
) -> ChatSessionRead:
    if space.space_id is None:
        raise IllegalStateError()

    result = await service.create_chat_session(space=space, title=body.title)

    return result


@router.get(
    "/{space_id}/sessions",
    summary="세션 목록 조회",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_200_OK: {
            "model": PaginationResponse[ChatSessionRead],
            "description": "세션 목록 조회 성공",
        }
    },
)
async def get_chat_sessions(
    space: Annotated[ChatSpace, Depends(chat_space_from_space_id_path)],
    service: Annotated[ChatService, Depends(ChatService.factory)],
    pagination: Annotated[PaginationParams, Query()],
) -> PaginationResponse[ChatSessionRead]:
    if space.space_id is None:
        raise IllegalStateError()

    offset = (pagination.page - 1) * pagination.size
    limit = pagination.size

    result = await service.get_chat_sessions(space=space, offset=offset, limit=limit)

    return PaginationResponse(
        data=result,
        page=pagination.page,
        size=pagination.size
    )
