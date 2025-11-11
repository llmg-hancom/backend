from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, update, col

from core.config import settings
from models.refresh_token import RefreshToken
from utils.auth import create_jwt, create_refresh_token, hash_refresh_token


@dataclass
class Tokens:
    access_token: str
    refresh_token: str


def token_regenerate(user_id: int, token_id: int | None, db: Session) -> Tokens:
    # 액세스 토큰 생성
    access_token = create_jwt(user_id)

    # 리프레시 토큰 생성
    refresh_token = create_refresh_token()

    # 사용한 리프레시 토큰을 revoke
    if token_id is not None:
        db.exec(
            update(RefreshToken)
            .where(col(RefreshToken.token_id) == token_id)
            .values({"is_revoked": True})
        )

    # 생성한 리프레시 토큰을 데이터베이스에 추가
    refresh_token_model = RefreshToken(
        user_id=user_id,
        token_hash=hash_refresh_token(refresh_token),
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAY),
    )

    db.add(refresh_token_model)
    db.commit()

    return Tokens(access_token=access_token, refresh_token=refresh_token)
