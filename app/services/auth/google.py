from dataclasses import dataclass
from urllib.parse import urlencode

from pydantic import EmailStr
import requests
from sqlmodel import Session, select

from core.config import settings
from models.social_account import SocialAccount, SocialAccountProvider
from models.user import User, UserRead
from utils.auth import create_jwt


@dataclass
class LoginSuccess:
    token: str
    token_type: str
    user: UserRead


def login_with_google_callback(code: str, db: Session) -> LoginSuccess:
    access_token = code_to_access_token(code)
    user_info = get_user_info(access_token)

    social_account = db.exec(
        select(SocialAccount)
        .where(SocialAccount.provider == SocialAccountProvider.GOOGLE)
        .where(SocialAccount.provider_id == user_info.id)
    ).one_or_none()

    if social_account is None:
        # 이메일을 바탕으로 user를 찾는다.
        user = db.exec(select(User).where(User.email == user_info.email)).one_or_none()

        # user가 없으면 회원가입을 진행한다.
        if user is None:
            user = User(
                email=user_info.email, nickname=user_info.name, hashed_password=None
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        # social_account를 생성한다.
        social_account = SocialAccount(
            provider=SocialAccountProvider.GOOGLE,
            provider_id=user_info.id,
            user_id=user.id,
        )
        db.add(social_account)
        db.commit()
        db.refresh(social_account)

    # user를 반환한다.
    return LoginSuccess(
        token=create_jwt(social_account.user_id),
        token_type="bearer",
        user=UserRead.model_validate(social_account.user),
    )


def code_to_access_token(code: str) -> str:
    code_to_token_url = "https://oauth2.googleapis.com/token"
    body = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "redirect_uri": "http://localhost:8000/v1/auth/google/callback",
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }

    response = requests.post(code_to_token_url, data=urlencode(body), headers=headers)
    response.raise_for_status()
    return response.json()["access_token"]


@dataclass
class UserInfo:
    id: str
    email: EmailStr
    name: str


def get_user_info(access_token: str) -> UserInfo:
    user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    response = requests.get(user_info_url, headers=headers)
    response.raise_for_status()
    response_json = response.json()
    return UserInfo(
        id=response_json["id"], email=response_json["email"], name=response_json["name"]
    )
