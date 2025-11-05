from pydantic import BaseModel, Field


class LivenessResponse(BaseModel):
    status: str = Field(default="ok", description="서버 상태")
