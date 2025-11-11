from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import TIMESTAMP, Column, UniqueConstraint, func
from sqlmodel import Enum as SaEnum
from sqlmodel import Field, Relationship, SQLModel


if TYPE_CHECKING:
    from models.user import User


class SocialAccountProvider(str, Enum):
    GOOGLE = "google"


class SocialAccountBase(SQLModel):
    pass


class SocialAccount(SocialAccountBase, table=True):
    __tablename__ = "social_accounts"
    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_id", name="social_accounts_provider_provider_id_key"
        ),
    )

    social_account_id: Optional[int] = Field(
        default=None, primary_key=True, description="소셜 로그인 아이디"
    )
    user_id: int = Field(foreign_key="users.user_id", nullable=False)
    provider: SocialAccountProvider = Field(
        default=SocialAccountProvider.GOOGLE,
        sa_column=Column(SaEnum(SocialAccountProvider)),
    )
    provider_id: str = Field(max_length=255, nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        sa_column=Column(
            TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
        ),
    )

    user: "User" = Relationship(back_populates="social_accounts")
