from fastapi import status

from errors.base import BackendBaseError


class NotReadyError(BackendBaseError):
    """서버가 아직 요청을 받을 준비가 되지 않음"""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="NOT_READY",
            message="서버가 아직 요청을 받을 준비가 되지 않았습니다."
        )
