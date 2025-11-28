import uuid
from contextlib import contextmanager
from pathlib import Path
import shutil
import time
from typing import Literal


from celery.utils.log import get_task_logger


# from models.document_chunk import DocumentChunk
# from rag.embedding import embed_texts  # (BGE-m3-ko 1024d)
from rag.cleaning import (
    clean_common_noise,
    clean_rag_text,
    process_html_with_tables,
)
from sqlmodel import Session
from workers.celery_app import celery_app

from db.session import engine
from models.document import Document, DocumentStatus
from services.document.storage_service import storage_service

# (Chunking 로직은 별도 파일로 분리하거나 여기에 구현해야 함)
# from rag.chunking import get_chunks_from_structured_data

logger = get_task_logger(__name__)


# --- DB 세션 관리를 위한 컨텍스트 매니저 ---
@contextmanager
def get_db_session():
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            raise


# 임시 파일 저장 경로
DOWNLOAD_DIR = Path("/tmp/hwp-tasks")


def _download_from_s3(file_uri: str, local_file_dir: Path) -> Path:
    logger.info(f"{file_uri}를 {local_file_dir} 디렉토리로 다운로드 중...")
    try:
        local_path: Path = storage_service.download_file(file_uri, local_file_dir)
        return local_path
    except Exception as e:
        logger.error(f"{file_uri} 다운로드 실패: {e}")
        raise e


def _upload_tmp_s3(local_file: Path, ext: Literal["txt", "json"] = "txt") -> str:
    logger.info(f"{local_file}를 S3에 업로드 중...")
    unique_name = uuid.uuid4()
    file_key = f"tmp/{ext}/{unique_name}.{ext}"
    try:
        s3_path = storage_service.upload_local_file(local_file, file_key)
        logger.info(f"{local_file}를 업로드 성공")
        return s3_path
    except Exception as e:
        logger.error(f"{local_file} 업로드 실패: {e}")
        raise e


# noinspection PyUnresolvedReferences
def _extract_text_from_hwpx(local_hwpx_path: Path) -> Path:
    import jpype.imports  # noqa: F401
    from kr.dogfoot.hwpxlib.reader import HWPXReader
    from kr.dogfoot.hwpxlib.tool.textextractor import (
        TextExtractMethod,
        TextExtractor,
        TextMarks,
    )

    logger.info(f"OWPML 필터로 {local_hwpx_path}에서 텍스트 추출 중...")

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
    try:
        hwpx_file = HWPXReader.fromFilepath(str(local_hwpx_path))
        hwpxtext = str(
            TextExtractor.extract(hwpx_file, text_extract_method, True, text_marks)
        )
        hwpxtext: str = clean_rag_text(hwpxtext)
        hwpxtext = clean_common_noise(hwpxtext)
        hwpxtext = process_html_with_tables(hwpxtext)
        txt_path = local_hwpx_path.with_suffix(".txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(hwpxtext)
        logger.info(f"{txt_path}에 텍스트 추출 결과 저장")
        return txt_path
    except Exception as e:
        logger.error(f"{local_hwpx_path}에서 텍스트 추출 실패")
        raise e


SUPPORTED_EXTENSIONS = (".hwp", ".hwpx", ".txt")


def _process_selector(file_path: Path):
    if file_path.suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"지원하지 않는 확장자입니다: {file_path.suffix}")
    if file_path.suffix == ".hwp":
        local_hwpx_path = _convert_hwp_to_hwpx(file_path)
        final_path = _extract_text_from_hwpx(local_hwpx_path)
    elif file_path.suffix == ".hwpx":
        final_path = _extract_text_from_hwpx(file_path)
    else:  # 이미 txt파일 인 경우
        final_path = file_path
    return final_path


# noinspection PyUnresolvedReferences
def _convert_hwp_to_hwpx(local_hwp_path: Path) -> Path:
    import jpype.imports  # noqa: F401
    from kr.dogfoot.hwp2hwpx import Hwp2Hwpx
    from kr.dogfoot.hwplib.object import HWPFile
    from kr.dogfoot.hwplib.reader import HWPReader
    from kr.dogfoot.hwpxlib.object import HWPXFile
    from kr.dogfoot.hwpxlib.writer import HWPXWriter

    try:
        local_hwpx_path = local_hwp_path.with_suffix(".hwpx")
        logger.info(f".hwp를 .hwpx로 변환 중: {local_hwpx_path}")
        fromFile: HWPFile = HWPReader.fromFile(str(local_hwp_path))
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


@celery_app.task(name="process-document-task", bind=True, max_retries=3)
def process_document(self, doc_id: int) -> str:
    """
    hwp/hwpx 문서를 txt로 변환해서 s3에 올리는 작업
    """
    logger.info(f"[TASK_START] 문서 txt 변환 시작: (doc_id: {doc_id})")
    # 임시 디렉토리 생성
    file_dir = DOWNLOAD_DIR / f"{doc_id}_{time.time()}"
    file_dir.mkdir(parents=True)

    # [핵심] 결과 저장을 위해 DB 세션 시작
    try:
        with get_db_session() as db:
            doc = db.get(Document, doc_id)
            if not doc:
                logger.error(f"문서를 찾을 수 없음: (doc_id: {doc_id})")
                raise Exception
            if doc.status == DocumentStatus.ready:
                logger.warning(f"이미 'ready' 상태의 문서임: (doc_id: {doc_id})")
                raise Exception
            elif doc.status == DocumentStatus.pending:
                logger.info(f"문서 처리 중...: (doc_id: {doc_id})")
                doc.status = DocumentStatus.processing
                db.flush()
            local_path = _download_from_s3(doc.file_path, file_dir)
        txt_path = _process_selector(local_path)
        s3_txt_path = _upload_tmp_s3(txt_path)
        logger.info(f"[TASK_SUCCESS] 문서 txt 변환 완료: (doc_id: {doc_id})")
        return str(s3_txt_path)
    except FileNotFoundError as e:
        raise self.retry(exc=e, countdown=2)
    except Exception as e:
        logger.error(f"[TASK_FAILED] 문서 txt 변환 실패: (doc_id: {doc_id}) - {e}")
        raise e
    finally:
        _cleanup_temp_dir(file_dir)
