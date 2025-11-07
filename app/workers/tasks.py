import logging
import os
from pathlib import Path

import jpype
import jpype.imports

# from workers.celery_app import celery_app
# from db.session import SessionLocal
# from models.document import Documents
# from models.document_chunk import DocumentChunk
# from rag.embedding import embed_texts  # (BGE-m3-ko 1024d)
from rag.cleaning import clean_common_noise, clean_rag_text

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


def _extract_text_from_hwpx(local_hwpx_path: Path | str) -> str:
    logger.info(f"OWPML 필터로 {local_hwpx_path}에서 텍스트 추출 중...")
    hwpx_file = HWPXReader.fromFilepath(str(local_hwpx_path))
    hwpxtext = TextExtractor.extract(hwpx_file, text_extract_method, True, text_marks)
    hwpxtext = clean_rag_text(hwpxtext)
    hwpxtext = clean_common_noise(hwpxtext)
    return hwpxtext