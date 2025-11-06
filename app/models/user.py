from sqlmodel import Field, Relationship, SQLModel
from sqlalchemy import Column, TIMESTAMP, func
from pydantic import EmailStr
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from enum import Enum

if TYPE_CHECKING:
    from models.social_account import SocialAccount
    from models.document import Document
    from models.group import Group
    from models.group_member import GroupMember
    from models.chat_space import ChatSpace
    from models.chat_session import ChatSession
    from models.chat_space_document import ChatSpaceDocument


class UserBase(SQLModel):
    email: EmailStr = Field(
        max_length=255,
        sa_column_kwargs={"unique": True},
        index=True,
        description="유저 이메일",
    )
    nickname: str = Field(
        max_length=100,
        index=True,
        description="닉네임",
    )


class User(UserBase, table=True):
    __tablename__ = "users"
    user_id: Optional[int] = Field(
        default=None, primary_key=True, description="유저 ID"
    )
    password_hash: Optional[str] = Field(
        default=None,
        max_length=255,
        description="해시된 비밀번호. 소셜 로그인일 경우 NULL이 들어감",
    )
    is_active: bool = Field(default=True, description="활성화 여부")
    created_at: datetime = Field(
        sa_column=Column(
            TIMESTAMP(timezone=True),
            server_default=func.now(),  # noqa: F821
            nullable=False,
        ),
        description="유저 생성 시간",
    )
    deleted_at: Optional[datetime] = Field(
        default=None, sa_column=Column(TIMESTAMP(timezone=True), index=True)
    )

    # Relationships
    social_accounts: list["SocialAccount"] = Relationship(
        back_populates="user", sa_relationship_kwargs={"cascade": "all, delete"}
    )
    refresh_tokens: list["RefreshToken"] = Relationship(
        back_populates="user", sa_relationship_kwargs={"cascade": "all, delete"}
    )
    created_groups: list["Group"] = Relationship(
        back_populates="created_by_user",
        sa_relationship_kwargs={"foreign_keys": "[Group.created_by_user_id]"},
    )
    group_memberships: list["GroupMember"] = Relationship(
        back_populates="user", sa_relationship_kwargs={"cascade": "all, delete"}
    )
    uploaded_documents: list["Document"] = Relationship(
        back_populates="uploaded_by_user",
        sa_relationship_kwargs={"foreign_keys": "[Document.uploaded_by_user_id]"},
    )
    owned_chat_spaces: list["ChatSpace"] = Relationship(
        back_populates="owner_user",
        sa_relationship_kwargs={
            "cascade": "all, delete",
            "foreign_keys": "[ChatSpace.owner_user_id]",
        },
    )
    chat_space_documents_added: list["ChatSpaceDocument"] = Relationship(
        back_populates="added_by_user",
        sa_relationship_kwargs={"foreign_keys": "[ChatSpaceDocument.added_by_user_id]"},
    )
    chat_sessions: list["ChatSession"] = Relationship(back_populates="user")


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
    user: User = Relationship(back_populates="refresh_tokens")


class UserRead(UserBase):
    user_id: Optional[int] = Field(
        default=None, primary_key=True, description="유저 ID"
    )
    created_at: datetime = Field(description="유저 생성 시간")


class UserWrite(UserBase):
    email: EmailStr = Field(description="유저 이메일")
    nickname: str = Field(description="닉네임")
    hashed_password: str = Field(description="해시된 비밀번호")
