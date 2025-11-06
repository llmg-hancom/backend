import os
from pathlib import Path
import sys

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv


def test_s3_upload():
    """
    .env 파일에서 AWS 자격 증명을 로드하여 S3에 테스트 파일을 업로드합니다.
    """

    # --- 1. .env 파일 로드 ---
    # 이 스크립트가 .env 파일과 같은 위치에 있다고 가정합니다.
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        env_path = ".env"  # VSCode 등에서 직접 실행 시
        if not os.path.exists(env_path):
            print("오류: .env 파일을 찾을 수 없습니다. .env와 같은 폴더에 넣어주세요.")
            return

    load_dotenv(env_path)
    print(f".env 파일 로드 완료: {env_path}")

    # --- 2. 환경 변수 읽기 (aws-s3-iam-setup.md 4단계 참조) ---
    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_s3_bucket_name = os.getenv("AWS_S3_BUCKET_NAME")
    aws_region = os.getenv("AWS_REGION")

    # --- 3. 설정 값 검증 ---
    if not all(
        [
            aws_access_key_id,
            aws_secret_access_key,
            aws_s3_bucket_name,
            aws_region,
        ]
    ):
        print("\n--- [오류] ---")
        print("필수 .env 변수 중 일부가 설정되지 않았습니다.")
        print(
            "AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_S3_BUCKET_NAME, AWS_REGION을 확인하세요."
        )
        sys.exit(1)

    print(f"S3 버킷: {aws_s3_bucket_name}")
    print(f"리전: {aws_region}")
    print(f"Access Key ID: {aws_access_key_id[:4]}...{aws_access_key_id[-4:]}")

    # --- 4. 테스트용 로컬 파일 생성 ---
    local_file_path = Path("../testfiles/2023년 디지털정부 발전유공 포상 추진계획.hwpx")
    s3_object_key = (
        "public/2023년 디지털정부 발전유공 포상 추진계획.hwpx"  # S3에 저장될 경로
    )

    try:
        # with open(local_file_path, "w", encoding="utf-8") as f:
        #     f.write("이 파일은 FastAPI 백엔드의 S3 연결을 테스트하기 위한 것입니다.\n")
        #     f.write(f"버킷: {aws_s3_bucket_name}\n")
        print(f"\n테스트용 로컬 파일: {local_file_path}")

        # --- 5. Boto3 S3 클라이언트 초기화 ---
        # boto3는 환경 변수에서 자격 증명을 자동으로 읽어옵니다.
        s3_client = boto3.client(
            "s3",
            region_name=aws_region,
            # aws_access_key_id, aws_secret_access_key는 자동으로 env에서 로드됨
        )

        # --- 6. 파일 업로드 시도 (WBS 3.3) ---
        print(
            f"'{local_file_path}' 파일을 's3://{aws_s3_bucket_name}/{s3_object_key}'로 업로드 시도..."
        )

        s3_client.upload_file(local_file_path, aws_s3_bucket_name, s3_object_key)

        print("\n--- [성공] ---")
        print("파일 업로드에 성공했습니다!")
        print(
            f"AWS S3 콘솔에서 s3://{aws_s3_bucket_name}/{s3_object_key} 경로를 확인하세요."
        )

    except NoCredentialsError:
        print("\n--- [오류] ---")
        print("AWS 자격 증명을 찾을 수 없습니다.")
        print(
            ".env 파일의 AWS_ACCESS_KEY_ID와 AWS_SECRET_ACCESS_KEY가 올바른지 확인하세요."
        )

    except ClientError as e:
        print("\n--- [오류] ---")
        error_code = e.response.get("Error", {}).get("Code")
        if error_code == "AccessDenied":
            print("S3 접근이 거부되었습니다 (AccessDenied).")
            print(
                f"IAM 사용자(fastapi-s3-worker)가 '{aws_s3_bucket_name}' 버킷에 's3:PutObject' 권한을 가졌는지 확인하세요."
            )
            print(f"IAM 정책: {e}")
        elif error_code == "NoSuchBucket":
            print(f"S3 버킷('{aws_s3_bucket_name}')을 찾을 수 없습니다.")
            print(
                ".env 파일의 버킷 이름이 1단계에서 생성한 이름과 동일한지 확인하세요."
            )
        else:
            print(f"Boto3 클라이언트 오류가 발생했습니다: {e}")

    except Exception as e:
        print(f"\n--- [알 수 없는 오류] ---")
        print(f"예상치 못한 오류가 발생했습니다: {e}")

    # finally:
    #     # --- 7. 로컬 테스트 파일 삭제 ---
    #     if os.path.exists(local_file_path):
    #         os.remove(local_file_path)
    #         print(f"\n로컬 테스트 파일 삭제: {local_file_path}")


if __name__ == "__main__":
    test_s3_upload()
