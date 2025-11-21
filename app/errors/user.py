from errors.base import BackendBaseError


class UserForbidden(BackendBaseError):
    def __init__(self):
        super().__init__(
            status_code=403,
            error_code="USER_FORBIDDEN",
            message="이 사용자를 조회할 권한이 없습니다."
        )
