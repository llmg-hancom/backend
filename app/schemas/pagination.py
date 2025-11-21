from pydantic import BaseModel, Field, computed_field


PAGINATION_MAX_SIZE: int = 100

class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    size: int = Field(default=10, ge=1, le=PAGINATION_MAX_SIZE)


class PaginationResponse[T](BaseModel):
    @computed_field
    @property
    def total(self) -> int:
        """응답의 총 데이터 수"""
        return len(self.data)

    page: int = Field(description="응답의 페이지 번호", ge=1)

    size: int = Field(description="응답의 페이지 최대 크기", ge=1, le=PAGINATION_MAX_SIZE)

    data: list[T] = Field(description="응답 데이터", default_factory=list)
