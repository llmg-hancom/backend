from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha3_256
import os

from sqlmodel import Session, select

from errors.auth import InvalidCridentialError, UserInactiveError
from models.refresh_token import RefreshToken
from models.user import User, UserRead
from services.auth.token import token_regenerate
from utils.auth import (
    create_jwt,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


@dataclass
class LoginSuccess:
    token: str
    refresh_token: str
    token_type: str
    user: UserRead


def login(email: str, password: str, db: Session) -> LoginSuccess:
    # 사용자 찾기
    user = db.exec(select(User).where(User.email == email)).first()

    # 유저가 존재하지 않는 경우
    if user is None:
        raise InvalidCridentialError()

    # 유저의 패스워드가 없는 경우 (소셜 로그인만 가능한 상태)
    if user.password_hash is None:
        raise InvalidCridentialError()

    # 비활성화된 유저인 경우
    if not user.is_active:
        raise UserInactiveError()

    # 비밀번호가 틀린 경우
    if not verify_password(password, user.password_hash):
        raise InvalidCridentialError()

    # user_id가 None일 경우
    if user.user_id is None:
        raise Exception("user name is None")

    # 토큰 생성
    tokens = token_regenerate(
        user_id=user.user_id,
        token_id=None,
        db=db
    )

    return LoginSuccess(
        token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type="bearer",
        user=UserRead.model_validate(user)
    )
