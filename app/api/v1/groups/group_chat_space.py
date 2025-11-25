from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, status

from models import Group
from schemas.chat import SpaceCreateRequest, SpaceRead
from schemas.pagination import PaginationParams, PaginationResponse
from services.chat_service import ChatService
from utils.group import get_group_from_group_id_path


router = APIRouter(
    prefix="/{group_id}/spaces",
    tags=["그룹", "채팅"]
)

@router.post(
    "",
    summary="그룹 챗스페이스 생성",
    status_code=status.HTTP_201_CREATED
)
async def create_space(
    group: Annotated[Group, Depends(get_group_from_group_id_path)],
    body: Annotated[SpaceCreateRequest, Body()],
    service: Annotated[ChatService, Depends(ChatService.factory)]
) -> SpaceRead:
    space = await service.create_group_chat_space(group, body.name)
    return SpaceRead.model_validate(space)


@router.get(
    "",
    summary="그룹 챗스페이스 목록 조회",
)
async def get_spaces(
    group: Annotated[Group, Depends(get_group_from_group_id_path)],
    page: Annotated[PaginationParams, Query()],
    service: Annotated[ChatService, Depends(ChatService.factory)]
) -> PaginationResponse[SpaceRead]:
    offset = (page.page - 1) * page.size
    limit = page.size

    spaces = await service.get_group_chat_spaces(
        group=group,
        offset=offset,
        limit=limit,
    )

    return PaginationResponse(
        page=page.page,
        size=page.size,
        data=[SpaceRead.model_validate(space) for space in spaces]
    )
