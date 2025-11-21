from typing import Annotated, Literal

from fastapi import Depends, Path, Security
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from db.session import get_async_db
from errors.auth import UserNotFoundError
from errors.general import IllegalStateError
from errors.user import UserForbidden
from models import User
from utils.auth import get_current_user


async def get_user_id_from_path(
    user_id: Annotated[int | Literal["me"], Path()],
    current_user: Annotated[User, Security(get_current_user)]
) -> int:
    if current_user.user_id is None:
        raise IllegalStateError()

    return current_user.user_id if user_id == "me" else user_id


async def get_user_from_user_id_path(
    user_id: Annotated[int, Depends(get_user_id_from_path)],
    current_user: Annotated[User, Security(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_async_db)]
) -> User:
    # 요청한 user_id와 인증된 사용자의 user_id가 다를 때
    if user_id != current_user.user_id:
        raise UserForbidden()

    query = (select(User).where(User.user_id == user_id))
    user = await session.scalar(query)

    if user is None:
        raise UserNotFoundError()

    return user
