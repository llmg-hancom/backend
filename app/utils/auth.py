from datetime import datetime, timedelta, timezone
from hashlib import sha3_256
import secrets
from typing import Annotated

from fastapi import Depends, Response
from fastapi.security import APIKeyCookie
import jwt
from pwdlib import PasswordHash
from sqlmodel import Session, select
from core.config import settings
from db.session import get_db
from errors.auth import InvalidTokenError, UserNotFoundError
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
        # subject는 string 타입이어야 함
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


def set_auth_cookie(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,
        samesite="lax",
        path="/",
        max_age=settings.JWT_EXPIRE_HOURS * 60 * 60,
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        path="/v1/auth/refresh",  # <- 해당 엔드포인트에서만 접근 가능
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAY * 24 * 60 * 60,
    )


def get_current_user(
    token: Annotated[str, Depends(APIKeyCookie(name="access_token"))],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )

        # subject는 string 타입이므로 검색 시 원래 타입인 int로 변환해야 함
        user_id = int(payload.get("sub"))

    except jwt.InvalidTokenError:
        raise InvalidTokenError()

    # int 타입 변환 실패한 경우
    except ValueError:
        raise InvalidTokenError()

    user = db.exec(select(User).where(User.user_id == user_id)).first()

    if not user:
        raise UserNotFoundError()

    return User.model_validate(user)
