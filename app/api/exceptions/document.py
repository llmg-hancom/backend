from fastapi import Request, status, FastAPI
from fastapi.responses import JSONResponse

from errors.document import (
    UnsupportedExtensionError,
    DuplicateFilesError,
    FileStorageError,
)


def unsupported_extension_error(_req: Request, _e: UnsupportedExtensionError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": "지원되지 않는 파일 형식입니다. .hwp 또는 .hwpx 파일만 업로드 가능합니다."
        },
    )


def duplicate_files_error(_req: Request, _e: DuplicateFilesError):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "이미 서버에 존재하는 파일입니다."},
    )


def file_storage_error(_req: Request, _e: FileStorageError):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "서버 스토리지 클라이언트 오류가 발생했습니다."},
    )


def document_exception_handler(app: FastAPI):
    app.add_exception_handler(UnsupportedExtensionError, unsupported_extension_error)
    app.add_exception_handler(DuplicateFilesError, duplicate_files_error)
    app.add_exception_handler(FileStorageError, file_storage_error)