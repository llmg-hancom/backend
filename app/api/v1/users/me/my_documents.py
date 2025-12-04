from typing import Annotated

from fastapi import APIRouter, Depends, Query, Security
from sqlmodel.ext.asyncio.session import AsyncSession

from db.session import get_async_db
from models.document import DocumentRead
from models.user import User
from schemas.pagination import PaginationParams, PaginationResponse
from services.document.get_users_docs import get_users_documents as service
from utils.auth import get_current_user


router = APIRouter()


@router.get(path="/documents", summary="현재 사용자의 문서 조회", tags=["문서"])
async def get_users_documents(
    pagination: Annotated[PaginationParams, Query()],
    user: Annotated[User, Security(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_async_db)],
) -> PaginationResponse[DocumentRead]:
    offset = (pagination.page - 1) * pagination.size
    limit = pagination.size

    data = await service(user=user, session=session, offset=offset, limit=limit)

    response_data = [DocumentRead.model_validate(doc) for doc in data]

    return PaginationResponse(
        page=pagination.page, size=pagination.size, data=response_data
    )
