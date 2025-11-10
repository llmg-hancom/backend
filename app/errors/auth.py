from fastapi import status

from base import BackendBaseError


class InvalidCridentialError(BackendBaseError):
    """아이디 또는 비밀번호가 일치하지 않음"""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="INVALID_CREDENTIAL",
            message="아이디 또는 비밀번호가 일치하지 않습니다."
        )


class InvalidTokenError(BackendBaseError):
    """토큰이 유효하지 않거나 만료되었음"""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="INVALID_TOKEN",
            message="토큰이 유효하지 않거나 만료되었습니다."
        )


class UserInactiveError(BackendBaseError):
    """사용자 계정이 비활성화 상태"""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="USER_INACTIVE",
            message="사용자 계정이 비활성화 상태입니다."
        )


class UserNotFoundError(BackendBaseError):
    """사용자 계정이 존재하지 않음"""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="USER_NOT_FOUND",
            message="사용자 계정이 존재하지 않습니다."
        )


class EmailAlreadyExistError(BackendBaseError):
    """회원 가입 중 이미 존재하는 이메일"""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            error_code="EMAIL_ALREADY_EXIST",
            message="이미 존재하는 이메일입니다."
        )


class RefreshTokenNotFoundError(BackendBaseError):
    """리프레시 토큰이 존재하지 않음"""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="REFRESH_TOKEN_NOT_FOUND",
            message="리프레시 토큰이 존재하지 않습니다."
        )


class RefreshTokenExpiredError(BackendBaseError):
    """리프레시 토큰이 만료되었음"""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="REFRESH_TOKEN_EXPIRED",
            message="리프레시 토큰이 만료되었습니다."
        )
