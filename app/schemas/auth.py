from typing import Annotated

from fastapi import Form
from pydantic import BaseModel, EmailStr, Field

from models.user import UserRead


class LoginRequest:
    def __init__(
        self, username: Annotated[EmailStr, Form()], password: Annotated[str, Form()]
    ):
        self.username = username
        self.password = password


class LoginResponse(BaseModel):
    access_token: str = Field(description="토큰 (JWT)")
    refresh_token: str = Field(description="리프레시 토큰")
    token_type: str = Field(description="토큰 타입")
    user: UserRead = Field(description="로그인한 사용자 정보")


class RegisterRequest(BaseModel):
    email: EmailStr = Field(description="이메일 주소")
    password: str = Field(description="비밀번호 (8자 이상)", min_length=8)
    nickname: str = Field(description="닉네임")


class LoginWithGoogleCallbackParam(BaseModel):
    code: str = Field(description="Google OAuth2 인증 코드")
    scope: str = Field(description="Google OAuth2 인증 범위")


class TokenRefreshRequest(BaseModel):
    refresh_token: str = Field(description="리프레시 토큰")


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(description="현재 비밀번호")
    new_password: str = Field(description="새 비밀번호 (8자 이상)", min_length=8)
