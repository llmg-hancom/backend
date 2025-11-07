from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from errors.auth import RefreshTokenExpiredError, RefreshTokenNotFoundError
from models.refresh_token import RefreshToken
from models.user import UserRead
from services.auth.token import token_regenerate
from utils.auth import (
    create_jwt,
    create_refresh_token,
    hash_refresh_token,
)


@dataclass
class RefreshSuccess:
    access_token: str
    refresh_token: str
    user: UserRead

def refresh_access_token(refresh_token: str, db: Session):
    refresh_token_hash = hash_refresh_token(refresh_token)
    refresh_token_model = db.exec(
        select(RefreshToken)
        .where(RefreshToken.token_hash == refresh_token_hash)
    ).one_or_none()

    # 리프레시 토큰이 존재하지 않음
    if not refresh_token_model:
        raise RefreshTokenNotFoundError()

    # 리프레시 토큰이 만료되었음
    if refresh_token_model.expires_at < datetime.now(timezone.utc):
        raise RefreshTokenExpiredError()

    # 토큰 재발급
    tokens = token_regenerate(refresh_token_model.user_id, db)

    return RefreshSuccess(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        user=UserRead.model_validate(refresh_token_model.user),
    )
