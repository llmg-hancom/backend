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
    """S3 클라이언트가 버킷에서 파일을 업로드/다운로드 할 수 없음"""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="INVALID_S3_CLIENT",
            message="S3 클라이언트 오류가 발생했습니다.",
        )



class DocumentNotFoundError(BackendBaseError):
    """문서를 찾을 수 없음"""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="DOCUMENT_NOT_FOUND",
            message="문서를 찾을 수 없습니다.",
        )


class ForbiddenDocumentAccessError(BackendBaseError):
    """문서에 접근할 권한이 없음(업로드한 유저가 아님)"""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="FORBIDDEN_DOCUMENT_ACCESS",
            message="문서에 접근할 권한이 없습니다.",
        )
