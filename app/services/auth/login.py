from dataclasses import dataclass

from errors.auth import InvalidCridentialError, UserInactiveError
from models.user import User, UserRead
from sqlmodel import Session, select
from utils.auth import create_jwt, verify_password


@dataclass
class LoginSuccess:
    token: str
    token_type: str
    user: UserRead


def login(email: str, password: str, db: Session) -> LoginSuccess:
    # 사용자 찾기
    user = db.exec(select(User).where(User.email == email)).first()

    # 유저가 존재하지 않는 경우
    if user is None:
        raise InvalidCridentialError()

    # 유저의 패스워드가 없는 경우 (소셜 로그인만 가능한 상태)
    if user.hashed_password is None:
        raise InvalidCridentialError()

    # 비활성화된 유저인 경우
    if not user.is_active:
        raise UserInactiveError()

    # 비밀번호가 틀린 경우
    if not verify_password(password, user.hashed_password):
        raise InvalidCridentialError()

    # 토큰 생성
    token = create_jwt(user.id)

    return LoginSuccess(
        token=token, token_type="bearer", user=UserRead.model_validate(user)
    )
