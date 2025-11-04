from fastapi import Depends, HTTPException, status, APIRouter
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session
from typing import Annotated
from models.user import UserRead, User
from db.session import get_db
from core.config import settings
from jwt import InvalidTokenError
import jwt


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/token")

router = APIRouter()


@router.get("/me", response_model=UserRead)
def get_user_info(
    token: Annotated[str, Depends(oauth2_scheme)], db: Session = Depends(get_db)
) -> UserRead:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception

    except InvalidTokenError:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()

    if user is None:
        raise credentials_exception

    return UserRead.model_validate(user)
