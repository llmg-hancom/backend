from sqlmodel import Session, select

from models import RefreshToken
from utils.auth import hash_refresh_token


def delete_token(refresh_token: str, db: Session) -> None:
    # 사용자로부터 받은 토큰을 해싱
    refresh_token_hash = hash_refresh_token(refresh_token)
    # 토큰이 존재하는지 확인
    refresh_token_model = db.exec(
        select(RefreshToken).where(RefreshToken.token_hash == refresh_token_hash)
    ).one_or_none()
    # 삭제할 토큰 revoke
    if refresh_token_model:
        refresh_token_model.is_revoked = True
        db.flush()

    return None
