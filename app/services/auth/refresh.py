from datetime import datetime, timezone

from pydantic import BaseModel
from sqlalchemy.orm import joinedload
from sqlmodel import Session, select

from errors.auth import (
    RefreshTokenExpiredError,
    RefreshTokenNotFoundError,
    UserNotFoundError,
)
from errors.general import IllegalStateError
from models.refresh_token import RefreshToken
from models.user import User
from services.auth.token import token_regenerate
from utils.auth import (
    hash_refresh_token,
)


class RefreshSuccess(BaseModel):
    access_token: str
    refresh_token: str
    user: User


def refresh_access_token(refresh_token: str, db: Session):
    # 사용자로부터 받은 토큰을 해싱
    refresh_token_hash = hash_refresh_token(refresh_token)

    # 토큰이 존재하는지 확인
    refresh_token_model = db.exec(
        select(RefreshToken)
        .where(RefreshToken.token_hash == refresh_token_hash)
        .options(joinedload(RefreshToken.user))  # type: ignore
    ).one_or_none()

    # 리프레시 토큰이 존재하지 않음
    if not refresh_token_model:
        raise RefreshTokenNotFoundError()

    # 리프레시 토큰이 만료되었음
    if (
        refresh_token_model.expires_at < datetime.now(timezone.utc)
        or refresh_token_model.is_revoked
    ):
        raise RefreshTokenExpiredError()

    # 토큰 ID가 존재하지 않음 (이론적으로 발생 불가)
    if refresh_token_model.token_id is None:
        raise IllegalStateError()

    # RefreshToken에 연결된 User 객체 조회 (cast로 타입 단언)
    user = RefreshToken.user
    if not user:
        # RefreshToken은 있는데 User가 없는 비정상적인 상황
        raise UserNotFoundError()

    # 토큰 재발급
    tokens = token_regenerate(
        user=user,
        token_id=refresh_token_model.token_id,
        db=db,
    )

    return RefreshSuccess(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        user=user,
    )
