from pydantic import BaseModel, EmailStr
from sqlmodel import Session, select

from errors.auth import EmailAlreadyExistError
from models.user import User
from utils.auth import hash_password


class RegisterSuccess(BaseModel):
    user: User


def register(
    email: EmailStr, password: str, nickname: str, db: Session
) -> RegisterSuccess:
    # 중복 확인
    existing_user = db.exec(select(User).where(User.email == email)).first()

    if existing_user:
        raise EmailAlreadyExistError()

    # 사용자 생성
    hashed_password = hash_password(password)
    user = User(
        email=email,
        nickname=nickname,
        password_hash=hashed_password,
    )

    db.add(user)
    db.flush()
    db.refresh(user)

    return RegisterSuccess(user=user)
