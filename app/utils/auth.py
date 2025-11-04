from typing import Annotated
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from uuid import UUID
from datetime import datetime, timedelta, timezone
from sqlmodel import Session
import jwt

from models.user import User
from db.session import get_db
from core.config import settings
from errors.auth import UserNotFoundError

hash = PasswordHash.recommended()


def hash_password(password: str | bytes) -> str:
    """비밀번호를 해시화합니다."""
    return hash.hash(password)


def verify_password(password: str | bytes, hashed_password: str) -> bool:
    """해시화된 비밀번호와 입력된 비밀번호를 비교합니다."""
    return hash.verify(password, hashed_password)


def create_jwt(user_id: UUID) -> str:
    """사용자를 위한 JWT 토큰을 생성합니다."""
    now = datetime.now(tz=timezone.utc)

    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(days=settings.JWT_EXPIRE_DAYS),
    }
    return jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


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

    except (jwt.InvalidTokenError, ValueError) as e:
        raise e

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise UserNotFoundError()

    return User.model_validate(user)
