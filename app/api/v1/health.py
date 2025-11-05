from fastapi import APIRouter
from schemas.health import LivenessResponse

router = APIRouter(prefix="/health", tags=["Health Check"])


@router.get(
    "/liveness",
    summary="서버 상태 확인",
    responses={
        200: {
            "description": "서버가 작동 중입니다.",
            "content": {
                "application/json": {
                    "example": LivenessResponse(status="ok").model_dump_json()
                }
            },
        }
    },
)
async def liveness_check() -> LivenessResponse:
    return LivenessResponse(status="ok")
