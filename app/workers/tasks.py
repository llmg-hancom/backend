import logging
import os
import shutil
from contextlib import contextmanager
from pathlib import Path
import jpype
import jpype.imports

from db.session import get_db

# from models.document import Documents
# from models.document_chunk import DocumentChunk
# from rag.embedding import embed_texts  # (BGE-m3-ko 1024d)
from rag.cleaning import clean_common_noise, clean_rag_text
from services.document.storage_service import storage_service
# from workers.celery_app import celery_app

# (Chunking 로직은 별도 파일로 분리하거나 여기에 구현해야 함)
# from rag.chunking import get_chunks_from_structured_data

# --- JVM 시작 (Celery 워커 부팅 시 1회 실행) ---
logger = logging.getLogger(__name__)

try:
    logger.info("[WORKER_BOOT] JVM 시작을 시도합니다...")

    # 1. Dockerfile의 ENV CLASSPATH="/app/resources/*" 설정을 사용
    classpath = os.environ.get("CLASSPATH")
    if not classpath:
        logger.warning(
            "CLASSPATH 환경 변수가 설정되지 않았습니다. /app/resources/*로 폴백합니다."
        )
        classpath = "/app/resources/*"

    if not jpype.isJVMStarted():
        jpype.startJVM(convertStrings=True)
        logger.info(f"[WORKER_BOOT] JVM이 {classpath}로 성공적으로 시작되었습니다.")
    else:
        logger.info("[WORKER_BOOT] JVM이 이미 실행 중입니다.")

    # 2. JVM 시작 후 Java 클래스 임포트 후 인스턴스화
    from kr.dogfoot.hwpxlib.reader import HWPXReader
    from kr.dogfoot.hwp2hwpx import Hwp2Hwpx
    from kr.dogfoot.hwplib.object import HWPFile
    from kr.dogfoot.hwpxlib.object import HWPXFile
    from kr.dogfoot.hwpxlib.writer import HWPXWriter
    from kr.dogfoot.hwpxlib.tool.textextractor import (
        TextExtractMethod,
        TextExtractor,
        TextMarks,
    )

    text_extract_method = TextExtractMethod.InsertControlTextBetweenParagraphText
    text_marks = (
        TextMarks()
        .lineBreakAnd("\n")
        .paraSeparatorAnd("\n\n")
        .tableStartAnd("<table>\n")
        .tableEndAnd("\n</table>")
        .tabAnd("\t")
        .containerStartAnd("\n\n")
        .containerEndAnd("\n\n")
        .fieldStartAnd("")
        .fieldEndAnd("")
    )

except ImportError as e:
    logger.error(
        f"[WORKER_BOOT_FAILED] Java 클래스를 임포트할 수 없습니다. .jar 파일이 CLASSPATH({classpath})에 있는지 확인하세요: {e}"
    )
    raise e
except Exception as e:
    logger.error(f"[WORKER_BOOT_FAILED] JVM 시작에 실패했습니다: {e}")
    raise e


# --- DB 세션 관리를 위한 컨텍스트 매니저 ---
@contextmanager
def get_db_session():
    db = get_db()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# 임시 파일 저장 경로
DOWNLOAD_DIR = Path("/tmp/hwp-tasks")


def _download_from_s3(task_id: str, file_uri: str) -> Path:
    file_dir: Path = DOWNLOAD_DIR / task_id
    # 임시 파일 디렉토리 생성
    file_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"{file_uri}를 {file_dir} 디렉토리로 다운로드 중...")
    try:
        local_path: Path = storage_service.download_file(file_uri, file_dir)
        logger.info(f"{local_path} 디렉토리로 다운로드 완료!")
        return local_path
    except Exception as e:
        logger.error(f"{file_uri} 다운로드 실패: {e}")
        raise e


def _extract_text_from_hwpx(local_hwpx_path: Path) -> str:
    logger.info(f"OWPML 필터로 {local_hwpx_path}에서 텍스트 추출 중...")
    try:
        hwpx_file = HWPXReader.fromFilepath(str(local_hwpx_path))
        hwpxtext: str = TextExtractor.extract(
            hwpx_file, text_extract_method, True, text_marks
        )
        hwpxtext: str = clean_rag_text(hwpxtext)
        hwpxtext: str = clean_common_noise(hwpxtext)
        return hwpxtext
    except Exception as e:
        logger.error(f"{local_hwpx_path}에서 텍스트 추출 실패")
        raise e


def _convert_hwp_to_hwpx(local_hwp_path: Path) -> Path:
    try:
        local_hwpx_path = local_hwp_path.with_suffix(".hwpx")
        logger.info(f".hwp를 .hwpx로 변환 중: {local_hwpx_path}")
        fromFile: HWPFile = HWPXReader.fromFile(str(local_hwp_path))
        toFile: HWPXFile = Hwp2Hwpx.toHWPX(fromFile)
        HWPXWriter.toFilepath(toFile, str(local_hwpx_path))
        return local_hwpx_path
    except Exception as e:
        logger.error(f"{local_hwp_path}를 .hwpx로 변환 실패: {e}")
        raise e


def _cleanup_temp_dir(temp_dir: Path):
    logger.info(f"임시 디렉토리 {temp_dir} 정리 중...")
    if temp_dir.exists():
        shutil.rmtree(str(temp_dir))


# @celery_app.task(name="process_document_task")
# def process_document(doc_id: int):
#     """
#     [WBS 3.2, 3.4]
#     문서를 처리하여 RAG DB (pgvector)에 저장하는 메인 태스크
#     """
#     logger.info(f"[TASK_START] 문서 처리 시작: (doc_id: {doc_id})")
#
#     # [핵심] 결과 저장을 위해 DB 세션 시작
#     with get_db_session() as db:
#         doc = db.get(Document, doc_id)
#         if not doc:
#             logger.error(f"문서를 찾을 수 없음: (doc_id: {doc_id})")
#             return