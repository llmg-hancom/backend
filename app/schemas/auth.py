from pydantic import BaseModel, EmailStr, Field
from models.user import UserRead


class LoginRequest(BaseModel):
    email: EmailStr = Field(description="사용자의 이메일 주소")
    password: str = Field(description="사용자의 비밀번호")


class LoginResponse(BaseModel):
    token: str = Field(description="토큰 (JWT)")
    token_type: str = Field(description="토큰 타입")
    user: UserRead = Field(description="로그인한 사용자 정보")


class RegisterRequest(BaseModel):
    email: EmailStr = Field(description="이메일 주소")
    password: str = Field(description="비밀번호 (8자 이상)", min_length=8)
    nickname: str = Field(description="닉네임")
