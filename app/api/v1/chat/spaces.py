from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Security, Path, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from db.session import get_async_db
from errors.chat import SpaceNotFoundError, ForbiddenSpaceAccessError
from models import User, ChatSpace
from schemas.chat import SpaceRead
from utils.auth import get_current_user

router = APIRouter(prefix="/spaces")


@router.post(path="", summary="새 채팅방 생성", response_model=SpaceRead)
async def create_space(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[User, Security(get_current_user)],
    name: str,
) -> SpaceRead:
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