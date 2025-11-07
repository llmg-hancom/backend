class InvalidCridentialError(Exception):
    """아이디 또는 비밀번호가 일치하지 않음"""

    pass


class InvalidTokenError(Exception):
    """토큰이 유효하지 않거나 만료되었음"""

    pass


class UserInactiveError(Exception):
    """사용자 계정이 비활성화 상태"""

    pass


class UserNotFoundError(Exception):
    """사용자 계정이 존재하지 않음"""

    pass


class EmailAlreadyExistError(Exception):
    """회원 가입 중 이미 존재하는 이메일"""

    pass


class RefreshTokenNotFoundError(Exception):
    """리프레시 토큰이 존재하지 않음"""

    pass


class RefreshTokenExpiredError(Exception):
    """리프레시 토큰이 만료되었음"""

    pass
