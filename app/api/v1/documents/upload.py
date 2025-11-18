import hashlib

import uuid
from typing import Annotated

from fastapi import APIRouter, status, UploadFile, File, Depends, Security
from sqlalchemy.util.concurrency import asyncio
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from db.session import get_async_db
from errors.document import UnsupportedExtensionError, DuplicateFilesError
from models.document import Document
from models.user import User
from schemas.document import UploadResponse
from services.document.storage_service import storage_service
from workers.tasks import process_document
from utils.auth import get_current_user

router = APIRouter()

supported_extensions = (".hwp", ".hwpx", ".txt")


@router.post(
    path="/",
    status_code=status.HTTP_202_ACCEPTED,
    summary="문서 업로드",
)
async def upload_documents(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    current_user: Annotated[
        User, Security(get_current_user)
    ],  # [보안] 로그인한 사용자만
    file: UploadFile = File(...),
) -> UploadResponse:
    """
    문서 업로드 엔드포인트 (document 저장 -> DB 기록 -> Celery 작업 요청)
    """
    # 1. 파일 유효성 검사 (확장자 등)
    if not file.filename.lower().endswith(supported_extensions):
        raise UnsupportedExtensionError()
    # 2. [해시 계산] 파일의 SHA-256 해시 계산 (중복 방지용)
    sha256_hash = hashlib.sha256()
    while chunk := await file.read(8192):  # 8KB씩 읽기
        sha256_hash.update(chunk)
    file_hash = sha256_hash.hexdigest()

    # [중요] 해시 계산 후 파일 포인터를 다시 처음으로 되돌려야 document 업로드 가능
    await file.seek(0)

    # 3. [중복 검사] DB에서 동일한 해시가 있는지 확인
    result = await db.exec(select(Document).where(Document.file_hash == file_hash))

    existing_doc = result.first()

    if existing_doc:
        raise DuplicateFilesError()

    # 4. [document 업로드] 고유한 document 경로 생성 및 업로드
    # 경로: private/user_{id}/{uuid}/{filename}
    unique_id = uuid.uuid4()
    file_key = f"private/user_{current_user.user_id}/{unique_id}/{file.filename}"

    s3_path = await storage_service.upload_file(file, file_key)

    # 5. [DB 저장] 메타데이터 저장
    new_doc = Document(
        file_name=file.filename,
        file_path=s3_path,
        file_hash=file_hash,
        uploaded_by_user_id=current_user.user_id,
        document_scope="private",  # 기본값은 개인 문서
        status="pending",  # 처리 대기 상태
    )
    db.add(new_doc)
    await db.flush()
    await db.refresh(new_doc)

    # 6. [비동기 작업 요청] Celery에 문서 처리(Embedding) 요청
    await asyncio.to_thread(process_document.delay, new_doc.document_id)

    # 7. [즉시 응답] 202 Accepted
    return UploadResponse(
        message="문서가 업로드되었으며, 처리 작업을 시작했습니다.",
        document_id=new_doc.document_id,
        file_name=new_doc.file_name,
        status=new_doc.status,
    )
