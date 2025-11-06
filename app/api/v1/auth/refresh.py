from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session

from db.session import get_db
from schemas.auth import LoginResponse, TokenRefreshRequest
from services.auth.refresh import refresh_access_token as refresh_service


router = APIRouter()


@router.post("/refresh")
def refresh_access_token(
    body: TokenRefreshRequest, db: Annotated[Session, Depends(get_db)]
) -> LoginResponse:
    result = refresh_service(body.refresh_token, db)

    return LoginResponse(
        access_token=result.access_token,
        token_type="Bearer",
        refresh_token=result.refresh_token,
        user=result.user
    )
