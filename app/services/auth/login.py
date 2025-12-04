from pydantic import BaseModel, EmailStr
from sqlmodel import Session, select

from errors.auth import InvalidCredentialError, UserInactiveError
from models.user import User
from services.auth.token import token_regenerate
from utils.auth import (
    verify_password,
)


class LoginSuccess(BaseModel):
    token: str
    refresh_token: str
    token_type: str
    user: User


def login(email: EmailStr, password: str, db: Session) -> LoginSuccess:
    # 사용자 찾기
    user = db.exec(select(User).where(User.email == email)).first()

    # 유저가 존재하지 않는 경우
    if user is None:
        raise InvalidCredentialError()

    # 유저의 패스워드가 없는 경우 (소셜 로그인만 가능한 상태)
    if user.password_hash is None:
        raise InvalidCredentialError()

    # 비활성화된 유저인 경우
    if not user.is_active:
        raise UserInactiveError()

    # 비밀번호가 틀린 경우
    if not verify_password(password, user.password_hash):
        raise InvalidCredentialError()

    # 토큰 생성
    tokens = token_regenerate(user=user, token_id=None, db=db)

    return LoginSuccess(
        token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type="bearer",
        user=user,
    )
