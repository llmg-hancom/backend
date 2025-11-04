from fastapi import HTTPException


class TokenInvalidException(HTTPException):
    def __init__(self):
        super().__init__(status_code=401, detail="Token invalid")


class LoginFailedException(HTTPException):
    def __init__(self):
        super().__init__(status_code=401, detail="Login failed")
