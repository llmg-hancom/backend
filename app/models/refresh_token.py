from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import TIMESTAMP, Column, Field, Relationship, SQLModel, func

if TYPE_CHECKING:
    from models.user import User


class RefreshToken(SQLModel, table=True):
    """1.3. RefreshTokens (OAuth2용 새로고침 토큰)"""

    __tablename__ = "refresh_tokens"

    token_id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.user_id", nullable=False)
    token_hash: str = Field(
        max_length=255, sa_column_kwargs={"unique": True}, nullable=False
    )
    expires_at: datetime = Field(
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False)
    )
    created_at: datetime = Field(
        sa_column=Column(
            TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
        )
    )
    is_revoked: bool = Field(default=False)

    # Relationship
    user: "User" = Relationship(back_populates="refresh_tokens")
