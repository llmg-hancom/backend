import boto3
from botocore.exceptions import NoCredentialsError, ClientError
from fastapi import UploadFile
from s3path import S3Path

from core.config import settings
import logging

from errors.document import FileStorageError

logger = logging.getLogger(__name__)

class StorageService:
    def __init__(self):
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        self.bucket_name = settings.AWS_S3_BUCKET_NAME

    async def upload_file(self, file: UploadFile, file_key: str) -> str:
        """
        파일을 S3에 업로드하고, 접근 가능한 s3:// 경로를 반환합니다.
        file_key: document 내 저장 경로 (예: private/user_1/uuid/file.hwp)
        """
        try:
            # [중요] UploadFile은 SpooledTemporaryFile 객체이므로
            # boto3의 upload_fileobj를 사용하여 스트리밍 업로드 가능
            self.s3_client.upload_fileobj(
                file.file,
                self.bucket_name,
                file_key,
                ExtraArgs={"ContentType": file.content_type} # MIME 타입 메타데이터 저장
            )
            s3_path = f"s3://{self.bucket_name}/{file_key}"
            logger.info(f"document 업로드 성공: {s3_path}")
            return s3_path

        except (NoCredentialsError, ClientError) as e:
            logger.error(f"document 업로드 실패: {e}")
            raise FileStorageError()
        except Exception as e:
             logger.error(f"알 수 없는 업로드 오류: {e}")
             raise Exception()

    def generate_presigned_url(self, pathstr: str, expiration=3600) -> str:
        """
        (옵션) 프론트엔드에서 document 파일을 직접 다운로드해야 할 때 사용할 임시 URL 생성
        """
        try:
            # s3://bucket_name/key 형식을 파싱
            if not pathstr.startswith("s3://"):
                 return ""
            s3_path = S3Path(pathstr)
            bucket = s3_path.bucket
            key = s3_path.key

            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket, 'Key': key},
                ExpiresIn=expiration
            )
            return url
        except Exception as e:
            logger.error(f"Presigned URL 생성 실패: {e}")
            return ""

# 싱글톤 인스턴스 생성
storage_service = StorageService()