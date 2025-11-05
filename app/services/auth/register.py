from sqlmodel import Session, select
from errors.auth import EmailAlreadyExistError
from models.user import User, UserRead
from utils.auth import hash_password
from dataclasses import dataclass


@dataclass
class RegisterSuccess:
    user: UserRead


def register(email: str, password: str, nickname: str, db: Session) -> RegisterSuccess:
    # 중복 확인
    existing_user = db.exec(select(User).where(User.email == email)).first()

    if existing_user:
        raise EmailAlreadyExistError()

    # 사용자 생성
    hashed_password = hash_password(password)
    user = User(
        email=email,
        nickname=nickname,
        hashed_password=hashed_password,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return RegisterSuccess(user=UserRead.model_validate(user))
