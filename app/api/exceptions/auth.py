from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from errors.auth import (
    EmailAlreadyExistError,
    InvalidCridentialError,
    InvalidTokenError,
    UserInactiveError,
    UserNotFoundError,
)


def invalid_credential_error(_req: Request, _e: InvalidCridentialError):
    return JSONResponse(
        status_code=401, content={"detail": "아이디 또는 비밀번호가 잘못되었습니다."}
    )

def invalid_token_error(_req: Request, _e: InvalidTokenError):
    return JSONResponse(
        status_code=401, content={"detail": "유효하지 않은 토큰입니다."}
    )


def user_inactive_error(_req: Request, _e: UserInactiveError):
    return JSONResponse(
        status_code=401, content={"detail": "사용자 계정이 비활성화되었습니다."}
    )


def user_not_found_error(_req: Request, _e: UserNotFoundError):
    return JSONResponse(
        status_code=404, content={"detail": "사용자를 찾을 수 없습니다."}
    )


def email_already_exist_error(_req: Request, _e: EmailAlreadyExistError):
    return JSONResponse(
        status_code=400, content={"detail": "이미 존재하는 이메일입니다."}
    )


def auth_exception_handler(app: FastAPI):
    app.add_exception_handler(InvalidCridentialError, invalid_credential_error)
    app.add_exception_handler(InvalidTokenError, invalid_token_error)
    app.add_exception_handler(UserInactiveError, user_inactive_error)
    app.add_exception_handler(UserNotFoundError, user_not_found_error)
    app.add_exception_handler(EmailAlreadyExistError, email_already_exist_error)
