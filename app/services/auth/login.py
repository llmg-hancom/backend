from sqlmodel import Session, select
from dataclasses import dataclass
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
        raise ValueError("이메일 또는 비밀번호가 올바르지 않습니다.")

    # 유저 활성화 여부 확인
    if not user.is_active:
        raise ValueError("사용자 계정이 비활성화되었습니다.")

    # 토큰 생성
    token = create_jwt(user.id)

    return LoginSuccess(
        token=token, token_type="bearer", user=UserRead.model_validate(user)
    )
