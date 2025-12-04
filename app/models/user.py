from datetime import datetime, timezone
from typing import TYPE_CHECKING

from pydantic import EmailStr
from sqlalchemy import TIMESTAMP, Column, func, Boolean, true, Index
from sqlmodel import Field, Relationship, SQLModel


if TYPE_CHECKING:
    from models.chat_session import ChatSession
    from models.chat_space import ChatSpace
    from models.chat_space_document import ChatSpaceDocument
    from models.document import Document
    from models.group import Group
    from models.group_member import GroupMember
    from models.refresh_token import RefreshToken
    from models.social_account import SocialAccount


class UserBase(SQLModel):
    email: EmailStr = Field(
        max_length=255,
        unique=True,
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
    user_id: int | None = Field(default=None, primary_key=True, description="유저 ID")
    password_hash: str | None = Field(
        default=None,
        max_length=255,
        description="해시된 비밀번호. 소셜 로그인일 경우 NULL이 들어감",
    )
    is_active: bool = Field(
        default=True,
        description="활성화 여부",
        sa_column=Column(Boolean, server_default=true()),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        sa_column=Column(
            TIMESTAMP(timezone=True),
            server_default=func.now(),  # noqa: F821
            nullable=False,
        ),
        description="유저 생성 시간",
    )
    deleted_at: datetime | None = Field(
        default=None,
        sa_column=Column(TIMESTAMP(timezone=True)),
        description="유저 탈퇴 시간",
    )

    # Relationships
    social_accounts: list["SocialAccount"] = Relationship(
        back_populates="user", cascade_delete=True
    )
    refresh_tokens: list["RefreshToken"] = Relationship(
        back_populates="user", cascade_delete=True
    )
    created_groups: list["Group"] = Relationship(
        back_populates="created_by_user",
        sa_relationship_kwargs={"foreign_keys": "[Group.created_by_user_id]"},
    )
    group_memberships: list["GroupMember"] = Relationship(
        back_populates="user", cascade_delete=True
    )
    uploaded_documents: list["Document"] = Relationship(
        back_populates="uploaded_by_user",
        sa_relationship_kwargs={"foreign_keys": "[Document.uploaded_by_user_id]"},
    )
    owned_chat_spaces: list["ChatSpace"] = Relationship(
        back_populates="owner_user",
        cascade_delete=True,
        sa_relationship_kwargs={
            "foreign_keys": "[ChatSpace.owner_user_id]",
        },
    )
    chat_space_documents_added: list["ChatSpaceDocument"] = Relationship(
        back_populates="added_by_user",
        sa_relationship_kwargs={"foreign_keys": "[ChatSpaceDocument.added_by_user_id]"},
    )
    chat_sessions: list["ChatSession"] = Relationship(back_populates="user")

    __table_args__ = (
        Index(
            "ix_users_deleted_at",
            "deleted_at",
            postgresql_where=Column("deleted_at").is_not(None),
        ),
    )


class UserRead(UserBase):
    user_id: int = Field(description="유저 ID")
    created_at: datetime = Field(description="유저 생성 시간")


class UserWrite(UserBase):
    email: EmailStr = Field(description="유저 이메일")
    nickname: str = Field(description="닉네임")
    hashed_password: str = Field(description="해시된 비밀번호")


class UserEdit(UserBase):
    email: EmailStr | None = None
    nickname: str | None = None
