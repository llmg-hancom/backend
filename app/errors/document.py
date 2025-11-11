from fastapi import status
from errors.base import BackendBaseError


class UnsupportedExtensionError(BackendBaseError):
    """지원하지 않는 파일 확장자를 업로드하려고 함"""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="UNSUPPORTED_FILE_EXTENSION",
            message="지원하지 않는 파일 형식입니다.",
        )


class DuplicateFilesError(BackendBaseError):
    """같은 파일을 중복으로 업로드하려고 함"""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            error_code="DUPLICATE_FILES",
            message="이미 서버에 존재하는 파일입니다.",
        )


class FileStorageError(BackendBaseError):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="INVALID_S3_SERVER",
            message="파일 스토리지 서버 오류가 발생했습니다.",
        )