from .base import BackendBaseError


class SpaceNotFoundError(BackendBaseError):
    def __init__(self, space_id: int):
        super().__init__(
            status_code=404,
            error_code="SPACE_NOT_FOUND",
            message=f"해당 스페이스(id={space_id})를 찾을 수 없습니다."
        )


class NotSpaceAdminError(BackendBaseError):
    def __init__(self):
        super().__init__(
            status_code=403,
            error_code="NOT_SPACE_ADMIN",
            message="스페이스의 관리자가 아닙니다."
        )
