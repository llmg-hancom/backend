from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, false
from sqlmodel import TIMESTAMP, Column, Field, Relationship, SQLModel, func


if TYPE_CHECKING:
    from models.user import User


class RefreshToken(SQLModel, table=True):
    """1.3. RefreshTokens (OAuth2용 새로고침 토큰)"""

    __tablename__ = "refresh_tokens"

    token_id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(
        foreign_key="users.user_id", nullable=False, index=True, ondelete="CASCADE"
    )
    token_hash: str = Field(max_length=255, unique=True, nullable=False)
    expires_at: datetime = Field(
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False, index=True)
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        sa_column=Column(
            TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
        ),
    )
    is_revoked: bool = Field(
        default=False, sa_column=Column(Boolean, server_default=false(), nullable=False)
    )

    # Relationship
    user: "User" = Relationship(back_populates="refresh_tokens")
