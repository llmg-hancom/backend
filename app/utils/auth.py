from datetime import datetime, timedelta, timezone
from hashlib import sha3_256
import secrets
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
import jwt
from pwdlib import PasswordHash
from sqlmodel import Session

from core.config import settings
from db.session import get_db
from errors.auth import InvalidCridentialError, InvalidTokenError, UserNotFoundError
from models.user import User


hash = PasswordHash.recommended()


def hash_password(password: str | bytes) -> str:
    """비밀번호를 해시화합니다."""
    return hash.hash(password)


def verify_password(password: str | bytes, hashed_password: str) -> bool:
    """해시화된 비밀번호와 입력된 비밀번호를 비교합니다."""
    return hash.verify(password, hashed_password)


def create_jwt(user_id: int) -> str:
    """사용자를 위한 JWT 토큰을 생성합니다."""
    now = datetime.now(tz=timezone.utc)

    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(hours=settings.JWT_EXPIRE_HOURS),
    }
    return jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


def create_refresh_token() -> str:
    """사용자를 위한 리프레시 토큰을 생성합니다."""
    return secrets.token_hex(64)


def hash_refresh_token(refresh_token: str) -> str:
    """리프레시 토큰을 sha3-256으로 해시화합니다."""
    return sha3_256(refresh_token.encode()).hexdigest()


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/token")


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        user_id = payload.get("sub")

    except jwt.InvalidTokenError:
        raise InvalidTokenError()

    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise UserNotFoundError()

    return User.model_validate(user)
