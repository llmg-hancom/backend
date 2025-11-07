from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session

from db.session import get_db
from schemas.auth import TokenRefreshRequest


router = APIRouter()


@router.post("/refresh")
def refresh_access_token(
    body: TokenRefreshRequest, db: Annotated[Session, Depends(get_db)]
):
    raise NotImplementedError()
