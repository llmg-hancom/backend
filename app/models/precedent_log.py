from datetime import date, datetime, timezone

from sqlalchemy import TIMESTAMP, Column, func
from sqlmodel import Field, SQLModel


class PrecedentLog(SQLModel, table=True):
    __tablename__ = "precedent_log"
    precedent_log_id: int | None = Field(
        default=None, primary_key=True, description="판례 로그 ID"
    )

    precedent_url: str | None = Field(
        default=None, max_length=1024, unique=True, description="판례 URL"
    )
    precedent_date: date = Field(description="판례 날짜")
    title: str = Field(max_length=255, description="")
    processed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            TIMESTAMP(timezone=True),
            server_default=func.now(),
            nullable=False,
        ),
        description="판례 작업 시간",
    )
