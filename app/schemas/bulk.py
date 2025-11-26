from typing import Annotated

from pydantic import BaseModel, Field


class BulkJobResponse[T](BaseModel):
    success: Annotated[list[T], Field(description="작업에 성공한 자원 목록", default_factory=list)]
    failed: Annotated[list[T], Field(description="작업에 실패한 자원 목록", default_factory=list)]
    skipped: Annotated[list[T], Field(description="작업을 생략한 자원 목록", default_factory=list)]
