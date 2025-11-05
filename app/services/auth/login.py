from sqlmodel import Session, select
from dataclasses import dataclass
from errors.auth import InvalidCridentialError, UserInactiveError
from models.user import User, UserRead
from utils.auth import verify_password, create_jwt


@dataclass
class LoginSuccess:
    token: str
    token_type: str
    user: UserRead


def login(email: str, password: str, db: Session) -> LoginSuccess:
    # 사용자 찾기
    user = db.exec(select(User).where(User.email == email)).first()

    if user is None or not verify_password(password, user.hashed_password):
        raise InvalidCridentialError()

    # 유저 활성화 여부 확인
    if not user.is_active:
        raise UserInactiveError()

    # 토큰 생성
    token = create_jwt(user.id)

    return LoginSuccess(
        token=token, token_type="bearer", user=UserRead.model_validate(user)
    )
