from urllib.parse import urlencode

from pydantic import EmailStr, BaseModel
import requests
from sqlmodel import Session, select

from core.config import settings
from errors.general import IllegalStateError
from models.social_account import SocialAccount, SocialAccountProvider
from models.user import User, UserRead
from utils.auth import create_jwt, create_refresh_token


class LoginSuccess(BaseModel):
    token: str
    refresh_token: str
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
                email=user_info.email, nickname=user_info.name, password_hash=None
            )

            db.add(user)
            db.flush()
            db.refresh(user)

        # model에서 정의한 user_id의 타입은 int | None이지만
        # 데이터베이스에 입력되면 반드시 primary key를 갖기 때문에
        # user_id가 None이 아니어야 한다.
        if user.user_id is None:
            raise IllegalStateError()

        # social_account를 생성한다.
        social_account = SocialAccount(
            provider=SocialAccountProvider.GOOGLE,
            provider_id=user_info.id,
            user_id=user.user_id,
        )

        db.add(social_account)
        db.flush()
        db.refresh(social_account, attribute_names=["user"])

    # user를 반환한다.
    return LoginSuccess(
        token=create_jwt(social_account.user_id),
        refresh_token=create_refresh_token(),
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
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }

    response = requests.post(code_to_token_url, data=urlencode(body), headers=headers)
    response.raise_for_status()
    return response.json()["access_token"]


class UserInfo(BaseModel):
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
