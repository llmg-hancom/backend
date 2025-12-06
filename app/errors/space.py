from fastapi import status

from errors.base import BackendBaseError


class ForbiddenSpaceAccessError(BackendBaseError):
    """스페이스에 접근할 권한이 없음"""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="FORBIDDEN_SPACE_ACCESS",
            message="스페이스에 접근할 권한이 없습니다.",
        )


class SpaceNotFoundError(BackendBaseError):
    def __init__(self, space_id: int):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="SPACE_NOT_FOUND",
            message=f"해당 스페이스(id={space_id})를 찾을 수 없습니다.",
        )


class NotSpaceAdminError(BackendBaseError):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="NOT_SPACE_ADMIN",
            message="스페이스의 관리자가 아닙니다.",
        )



