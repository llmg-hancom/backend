from sqlmodel import Session

from errors.auth import InvalidCredentialError
from errors.general import UnimplementedError
from models.user import User
from utils.auth import hash_password, verify_password


def change_my_password(
    change_user: User, old_password: str, new_password: str, session: Session
) -> None:
    if change_user.password_hash is None:
        raise UnimplementedError()

    password_correct = verify_password(
        password=old_password, hashed_password=change_user.password_hash
    )

    # 기존 비밀번호를 틀린 경우
    if not password_correct:
        raise InvalidCredentialError()

    change_user.password_hash = hash_password(new_password)

    _ = session.merge(change_user)
    session.flush()
