from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel
from sqlalchemy import Column, DateTime
from pydantic import EmailStr
from datetime import datetime, timezone
from uuid import UUID, uuid4
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.social_account import SocialAccount


class UserBase(SQLModel):
    email: EmailStr = Field(index=True, description="유저 이메일")
    nickname: str = Field(description="닉네임")

    __table_args__ = (UniqueConstraint("email"),)


class User(UserBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, description="유저 ID")
    hashed_password: str | None = Field(
        description="해시된 비밀번호. 소셜 로그인일 경우 NULL이 들어감"
    )
    is_active: bool = Field(default=True, description="활성화 여부")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="유저 생성 시간",
    )

    social_accounts: list["SocialAccount"] = Relationship(
        back_populates="user",
    )


class UserRead(UserBase):
    id: UUID = Field(description="유저 ID")
    created_at: datetime = Field(description="유저 생성 시간")


class UserWrite(UserBase):
    email: EmailStr = Field(description="유저 이메일")
    nickname: str = Field(description="닉네임")
    hashed_password: str = Field(description="해시된 비밀번호")
