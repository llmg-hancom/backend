from fastapi import status


class BackendBaseError(Exception):
    """백엔드의 기본 에러"""

    def __init__(
        self,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code: str = "UNKNOWN_ERROR",
        message: str = "알 수 없는 에러가 발생했습니다.",
    ):
        super().__init__()
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
