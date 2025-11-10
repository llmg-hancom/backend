from dataclasses import dataclass
from datetime import datetime, timezone

from sqlmodel import Session, select

from errors.auth import RefreshTokenExpiredError, RefreshTokenNotFoundError
from errors.general import IllegalStateError
from models.refresh_token import RefreshToken
from models.user import UserRead
from services.auth.token import token_regenerate
from utils.auth import (
    hash_refresh_token,
)


@dataclass
class RefreshSuccess:
    access_token: str
    refresh_token: str
    user: UserRead


def refresh_access_token(refresh_token: str, db: Session):
    # 사용자로부터 받은 토큰을 해싱
    refresh_token_hash = hash_refresh_token(refresh_token)

    # 토큰이 존재하는지 확인
    refresh_token_model = db.exec(
        select(RefreshToken).where(RefreshToken.token_hash == refresh_token_hash)
    ).one_or_none()

    # 리프레시 토큰이 존재하지 않음
    if not refresh_token_model:
        raise RefreshTokenNotFoundError()

    # 리프레시 토큰이 만료되었음
    if refresh_token_model.expires_at < datetime.now(timezone.utc):
        raise RefreshTokenExpiredError()

    # 리프레시 토큰이 revoke되었음
    if refresh_token_model.is_revoked:
        raise RefreshTokenExpiredError()

    # 토큰 ID가 존재하지 않음
    #
    # RefreshToken.token_id는 int | None 타입으로 지정되어 있는데
    # 데이터베이스에서 조회한 레코드는 항상 기본키를 가지므로
    # 실제로 운영 환경에서 이 값은 None이 될 수 없음.
    if refresh_token_model.token_id is None:
        raise IllegalStateError()

    # 토큰 재발급
    tokens = token_regenerate(
        user_id=refresh_token_model.user_id,
        token_id=refresh_token_model.token_id,
        db=db,
    )

    return RefreshSuccess(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        user=UserRead.model_validate(refresh_token_model.user),
    )
