from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlmodel import Session, select

from db.session import get_db
from errors.health import NotReadyError
from schemas.health import HealthResponse


router = APIRouter(prefix="/health", tags=["Health Check"])


@router.get(
    "/liveness",
    summary="서버 상태 확인",
    responses={
        status.HTTP_200_OK: {
            "description": "서버가 작동 중입니다.",
            "content": {
                "application/json": {
                    "example": HealthResponse(status="ok").model_dump_json()
                }
            },
        }
    },
)
async def liveness_check() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/readiness",
    summary="서버 준비 상태 확인",
    responses={
        status.HTTP_200_OK: {
            "description": "서버가 준비되었습니다.",
            "content": {
                "application/json": {
                    "example": HealthResponse(status="ok").model_dump_json()
                }
            },
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "서버가 준비되지 않았습니다.",
            "content": {
                "application/json": {"example": {"detail": "서비스 준비 중입니다."}}
            },
        },
    },
)
async def readiness_check(db: Annotated[Session, Depends(get_db)]) -> HealthResponse:
    """
    서버가 작동하는데 필요한 데이터베이스 등의 작동 여부를 확인하고
    준비되지 않은 경우 HTTP 503 응답을 반환합니다.
    """
    try:
        _database_check = db.exec(select(1))

        return HealthResponse(status="ok")

    except Exception:
        raise NotReadyError()
