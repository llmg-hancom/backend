from contextlib import contextmanager
import json
from pathlib import Path
import shutil
import time
from typing import Dict, List

import psycopg
from celery.utils.log import get_task_logger

from core.config import settings

# from models.document_chunk import DocumentChunk
# from rag.embedding import embed_texts  # (BGE-m3-ko 1024d)
from rag.cleaning import clean_common_noise, clean_rag_text
from sqlmodel import Session
from workers.celery_app import celery_app

from db.session import engine
from models.document import Document, DocumentStatus
from services.document.storage_service import storage_service

from tqdm import tqdm
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)
from langchain_ollama import OllamaEmbeddings
from pgvector.psycopg2 import register_vector
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
        logger.info(f"{local_path} 디렉토리로 다운로드 완료!")
        return local_path
    except Exception as e:
        logger.error(f"{file_uri} 다운로드 실패: {e}")
        raise e


# noinspection PyUnresolvedReferences
def _extract_text_from_hwpx(local_hwpx_path: Path) -> str:
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
        hwpxtext: str = clean_common_noise(hwpxtext)
        return hwpxtext
    except Exception as e:
        logger.error(f"{local_hwpx_path}에서 텍스트 추출 실패")
        raise e


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


@celery_app.task(name="process-document-task")
def process_document(doc_id: int):
    """
    문서를 처리하여 pgvector에 저장하는 메인 태스크
    """
    logger.info(f"[TASK_START] 문서 처리 시작: (doc_id: {doc_id})")
    # 임시 디렉토리 생성
    file_dir = DOWNLOAD_DIR / f"{doc_id}_{time.time()}"
    file_dir.mkdir(parents=True)

    # [핵심] 결과 저장을 위해 DB 세션 시작
    try:
        with get_db_session() as db:
            doc = db.get(Document, doc_id)
            if not doc:
                logger.error(f"문서를 찾을 수 없음: (doc_id: {doc_id})")
                return
            if doc.status == DocumentStatus.ready:
                logger.warning(f"이미 'ready' 상태의 문서임: (doc_id: {doc_id})")
                return
            elif doc.status == DocumentStatus.pending:
                logger.info(f"문서 처리 중...: (doc_id: {doc_id})")
                doc.status = DocumentStatus.processing
                db.flush()
            local_path = _download_from_s3(doc.file_path, file_dir)
            if local_path.suffix == ".hwp":
                local_hwpx_path = _convert_hwp_to_hwpx(local_path)
            else:
                local_hwpx_path = local_path
            extracted_text = _extract_text_from_hwpx(local_hwpx_path)
            # TODO: 청킹, 임베딩, 후 pgvector 삽입 개발 필요
            # --- 임시 개발용 코드 ---
            logger.info(f"텍스트 출력 결과:\n{extracted_text}")
            testDir = DOWNLOAD_DIR / "txtfiles"
            testDir.mkdir(parents=True, exist_ok=True)
            testPath = testDir / local_hwpx_path.with_suffix(".txt").name
            with open(testPath, "w", encoding="utf-8") as f:
                f.write(extracted_text)
            # --- 임시 개발용 코드 끝 ---
            logger.info(f"[TASK_SUCCESS] 문서 처리 완료: (doc_id: {doc_id})")
            doc.status = DocumentStatus.ready
    except Exception as e:
        logger.error(f"[TASK_FAILED] 문서 처리 실패: (doc_id: {doc_id}) - {e}")
        try:
            with get_db_session() as db:
                doc = db.get(Document, doc_id)
                if doc:
                    doc.status = DocumentStatus.error
        except Exception as db_e:
            logger.error(f"에러 상태 DB 업데이트 실패: {db_e}")
    finally:
        _cleanup_temp_dir(file_dir)


@celery_app.task(name="preprocess-text-to-markdown")
def celery_beat_test():
    logger.info("[EMBED] 텍스트 마크다운으로 변환 시작!")
    DB_HOST = "127.0.0.1"
    TARGET_DIR = "/tmp/law_precedent"

    process_and_insert_to_db(DB_HOST, TARGET_DIR, "__korean_precedents.json")
    logger.info("[EMBED] 텍스트 마크다운으로 변환 완료!")


def preprocess_text_to_markdown(text: str, header_keys: List[str]) -> str:
    processed_text = text
    for key in header_keys:
        processed_text = processed_text.replace(key, f"\n## {key.strip('【】:')}\n", 1)
    return processed_text.strip()


DEFAULT_HEADERS_TO_SPLIT_ON = [("##", "섹션명")]
JUDGMENT_HEADER_KEYS = [
    "【원고, 피상고인】",
    "【원고, 피공소인】",
    "【원고, 상고인】",
    "【피고, 피상고인】",
    "【피고, 공소인, 상고인】",
    "【피고, 상고인】",
    "【주 문】",
    "【이 유】",
    "【청구취지】",
    "【제1심판결】",
    "【변론종결】",
    "【청구취지 및 항소취지】",
    "【원심판결】",
    "【사 실】",
    "【원 심】",
]


def split_markdown_chunks_with_fallback(
    text: str,
    max_chunk_size: int = 500,
    chunk_overlap: int = 50,
    headers_to_split_on: List[tuple] = DEFAULT_HEADERS_TO_SPLIT_ON,
) -> List[Dict]:
    """
    MarkdownHeaderTextSplitter로 1차 분할 후, 최대 크기를 초과하는 청크에 대해
    RecursiveCharacterTextSplitter로 2차 분할을 적용합니다. (메타데이터 보존)
    """
    # 1차 분할
    md_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on, strip_headers=False
    )
    first_split_documents = md_splitter.split_text(text)

    # 2차 분할 초기화
    recursive_splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""],
        length_function=len,
    )
    final_chunks = []

    for doc in first_split_documents:
        content = doc.page_content
        metadata = doc.metadata

        if len(content) > max_chunk_size:
            second_split_documents = recursive_splitter.create_documents([content])
            for sub_doc in second_split_documents:
                sub_doc.metadata.update(metadata)
                final_chunks.append(
                    {"page_content": sub_doc.page_content, "metadata": sub_doc.metadata}
                )
        else:
            final_chunks.append({"page_content": content, "metadata": metadata})

    return final_chunks


def conn_embedding_model(db_host):
    """
    DB 및 임베딩 모델 연결을 초기화합니다.
    """
    # 2. 임베딩 클라이언트 초기화
    # ❗️ Ollama 접속 주소를 전달받은 db_host와 ollama_port로 설정
    OLLAMA_BASE_URL = settings.OLLAMA_BASE_URL
    OLLAMA_MODEL = "bge-m3:567m"
    DB_USER = settings.POSTGRES_USER
    DB_PASSWORD = settings.POSTGRES_PASSWORD
    DB_NAME = settings.POSTGRES_DB
    embeddings = OllamaEmbeddings(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL)
    logger.info(
        f"[EMBED] Ollama 임베딩 모델 '{OLLAMA_MODEL}' 초기화 완료. (URL: {OLLAMA_BASE_URL})"
    )

    # 3. DB 연결 정보 설정 (로컬 접속 정보 사용)
    DB_CONFIG = {
        "database": DB_NAME,
        "user": DB_USER,
        "password": DB_PASSWORD,
        # ❗️ 전달받은 호스트와 포트 사용
        "host": db_host,
        "port": settings.POSTGRES_PORT,
    }

    # 4. 데이터 삽입을 위한 psycopg2 연결
    conn = None
    cur = None
    try:
        conn = psycopg.connect(**DB_CONFIG)
        register_vector(conn)
        cur = conn.cursor()
    except Exception as e:
        logger.error(f"[EMBED] 데이터 삽입을 위한 DB 연결 실패: {e}")
        return embeddings, None, None

    return embeddings, conn, cur


# -------------------------------------------------------------
# 4. 메인 파이프라인 함수: 분할 및 DB 삽입
# -------------------------------------------------------------
def process_and_insert_to_db(db_host, target_directory, file_name):
    # --- 4-1. JSON 파일 로드 ---
    file_path = Path(target_directory) / file_name
    if not file_path.exists():
        logger.error(f"[EMBED] 파일을 찾을 수 없습니다: {file_path}")
        return
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data_list = json.load(f)
        logger.error(f"[EMBED] 총 {len(data_list)}개 항목 로드 완료.")
    except Exception as e:
        logger.error(f"[EMBED] JSON 로드 실패: {e}")
        return

    # --- 4-2. 임베딩 클라이언트 및 DB 연결 초기화 ---
    # ❗️ 로컬 호스트와 포트를 사용하여 연결 시도
    embeddings, conn, cur = conn_embedding_model(db_host)

    if not conn:  # DB 연결 실패 시 바로 종료
        return

    uploaded_chunks_count = 0

    # --- 4-3. 항목별 처리 (분할, 임베딩, 삽입) ---
    print(f"\n--- {len(data_list)}개 항목 처리 시작 ---")

    for item_data in tqdm(data_list, desc="Processing and Inserting"):
        # 0. document 테이블 삽입 준비 (항목당 1개의 document 생성 가정)
        try:
            insert_doc_query = """
            INSERT INTO documents (file_name, uploaded_by_user_id, document_scope, status) 
            VALUES (%s, %s, %s, %s)
            RETURNING document_id;"""

            # 파일 이름은 사건번호 또는 판례정보일련번호를 사용 (메타데이터에서 추출)
            file_name = item_data.get(
                "사건번호", f"id_{item_data.get('판례정보일련번호', 'unknown')}"
            )

            # status를 'processing'으로 시작하고, 성공 시 'ready'로 변경하는 로직을 추가할 수 있습니다.
            cur.execute(insert_doc_query, (file_name, 1, "precedent", "ready"))
            document_id = cur.fetchone()[0]

            if not document_id:
                logger.error("[EMBED] Documents 삽입 후 ID 반환 실패")
                raise Exception("Documents 삽입 후 ID 반환 실패")

            # 1. 분할할 텍스트 추출 및 기본 메타데이터 설정
            text_key = "전문"
            max_chunk_size = 1000
            full_text = item_data.pop(text_key, None)
            base_metadata = item_data.copy()

            if not full_text:
                logger.warning(f"\n'{text_key}' 키가 없어 항목을 건너뜁니다.")
                conn.rollback()
                continue

            # 2. 텍스트 전처리 및 분할 실행
            markdown_formatted_text = preprocess_text_to_markdown(
                full_text, JUDGMENT_HEADER_KEYS
            )
            chunks = split_markdown_chunks_with_fallback(
                text=markdown_formatted_text, max_chunk_size=max_chunk_size
            )

            # 3. 각 청크별 임베딩 생성 및 document_chunks 테이블에 삽입
            for chunk in chunks:
                chunk_content = chunk["page_content"]
                # print(f"chunk_content .. {chunk_content}") # 로그가 너무 많아질 수 있으므로 주석 처리
                # print(f"metadata .. {chunk['metadata']}") # 로그가 너무 많아질 수 있으므로 주석 처리

                # 임베딩 벡터 생성
                vector_data = embeddings.embed_query(chunk_content)

                # 메타데이터 병합 및 JSONB 변환
                combined_metadata = base_metadata.copy()
                combined_metadata.update(chunk["metadata"])
                metadata_json = json.dumps(combined_metadata, ensure_ascii=False)

                # document_chunks 삽입 쿼리
                insert_chunk_query = """
                INSERT INTO document_chunks 
                (document_id, content, embedding, meta) 
                VALUES (%s, %s, %s, %s);"""

                cur.execute(
                    insert_chunk_query,
                    (document_id, chunk_content, vector_data, metadata_json),
                )
                uploaded_chunks_count += 1

            conn.commit()  # ⭐️ 한 항목(document)에 대한 모든 청크 삽입이 성공하면 커밋

        except Exception as e:
            conn.rollback()  # ⚠️ 오류 발생 시 롤백 (이 항목의 모든 청크는 저장되지 않음)
            logger.error(
                f"\n[EMBED] 항목 처리 및 DB 삽입 실패 (사건번호: {item_data.get('사건번호', 'N/A')}) 상세: {e}"
            )
            continue # 다음 항목으로 넘어갑니다.

    # --- 4-4. 최종 정리 ---
    if conn:
        cur.close()
        conn.close()
    
    logger.info(f"\n[완료] 총 {len(data_list)}개 항목 중 {uploaded_chunks_count}개의 청크가 DB에 삽입되었습니다.")