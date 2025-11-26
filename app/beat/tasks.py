import json
from pathlib import Path
import psycopg
from celery.utils.log import get_task_logger

from core.config import settings

from workers.celery_app import celery_app


from tqdm import tqdm
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)
from langchain_ollama import OllamaEmbeddings
from pgvector.psycopg import register_vector

logger = get_task_logger(__name__)


@celery_app.task(name="preprocess-text-to-markdown")
def celery_beat_test():
    logger.info("[EMBED] 텍스트 마크다운으로 변환 시작!")
    TARGET_DIR = "/tmp/law_precedent"

    process_and_insert_to_db(TARGET_DIR, "__korean_precedents.json")
    logger.info("[EMBED] 텍스트 마크다운으로 변환 완료!")


def preprocess_text_to_markdown(text: str, header_keys: list[str]) -> str:
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
    headers_to_split_on: list[tuple[str, str]] = DEFAULT_HEADERS_TO_SPLIT_ON,
) -> list[dict]:
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


def conn_embedding_model():
    """
    DB 및 임베딩 모델 연결을 초기화합니다.
    """
    # 2. 임베딩 클라이언트 초기화
    OLLAMA_BASE_URL = settings.OLLAMA_BASE_URL
    OLLAMA_MODEL = "bge-m3:567m"
    embeddings = OllamaEmbeddings(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL)
    logger.info(
        f"[EMBED] Ollama 임베딩 모델 '{OLLAMA_MODEL}' 초기화 완료. (URL: {OLLAMA_BASE_URL})"
    )

    # 3. DB 연결 정보 설정 (로컬 접속 정보 사용)
    DB_CONFIG = {
        "dbname": settings.POSTGRES_DB,
        "user": settings.POSTGRES_USER,
        "password": settings.POSTGRES_PASSWORD,
        # ❗️ 전달받은 호스트와 포트 사용
        "host": settings.POSTGRES_HOST,
        "port": settings.POSTGRES_PORT,
    }

    # 4. 데이터 삽입을 위한 psycopg 연결
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
def process_and_insert_to_db(target_directory, file_name):
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
    embeddings, conn, cur = conn_embedding_model()

    if not conn:  # DB 연결 실패 시 바로 종료
        return

    uploaded_chunks_count = 0

    # --- 4-3. 항목별 처리 (분할, 임베딩, 삽입) ---
    logger.info(f"\n--- {len(data_list)}개 항목 처리 시작 ---")

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