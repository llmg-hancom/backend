from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path
import re
from typing import Any, Optional
from bs4 import BeautifulSoup
import requests
from requests.compat import urljoin
import psycopg
from celery.utils.log import get_task_logger
from psycopg import connection, cursor
from core.config import settings

# from models.document_chunk import DocumentChunk
# from rag.embedding import embed_texts  # (BGE-m3-ko 1024d)
from sqlmodel import Session
from workers.celery_app import celery_app

from db.session import engine

from tqdm import tqdm
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)
from langchain_ollama import OllamaEmbeddings
from pgvector.psycopg import register_vector
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


@celery_app.task(name="preprocess-text-to-markdown")
def celery_beat_test():
    logger.info("[EMBED] 텍스트 마크다운으로 변환 시작!")
    TARGET_DIR = "/tmp/law_precedent"

    # process_and_insert_to_db(TARGET_DIR, "__korean_precedents.json")
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
    # 여기 병합할때 수정 document_file_name_key, default_document_file_name_key 추가
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
            continue  # 다음 항목으로 넘어갑니다.

    # --- 4-4. 최종 정리 ---
    if conn:
        cur.close()
        conn.close()

    logger.info(
        f"\n[완료] 총 {len(data_list)}개 항목 중 {uploaded_chunks_count}개의 청크가 DB에 삽입되었습니다."
    )


# 새로 추가한 코드


def extract_case_number_from_contarea(soup):
    # 1. 원하는 요소 (td 클래스="contArea")를 찾습니다.
    cont_area_td = soup.select_one("td.contArea")

    if not cont_area_td:
        print("[ERROR] 'td.contArea' 영역을 찾을 수 없습니다.")
        return None

    # 2. contArea 내의 첫 번째 <p> 태그를 찾습니다.
    first_p_tag = cont_area_td.find("p")

    if not first_p_tag:
        print("[ERROR] 'td.contArea' 내에 첫 번째 <p> 태그를 찾을 수 없습니다.")
        return None
    raw_text = first_p_tag.get_text("\n\n", strip=True)
    # ⭐️ get_text()는 특정 태그(여기서는 <p>)와 그 하위 태그들 내의 모든 텍스트 노드들을
    # 하나로 합쳐서 반환합니다. 이때, 하나의 태그가 끝나고 다른 태그가 시작될 때
    # 해당 인자(여기서는 공백 문자 ' ')를 넣어 텍스트를 분리해 줍니다.
    # 4. 공백을 기준으로 문자열을 나눕니다.
    # split()은 연속된 공백을 하나로 처리합니다.
    parts = raw_text.split()

    if parts:
        # 첫 번째 항목을 판례번호로 추출합니다. (예: '2024다298448')
        case_number = parts[0]

        print(f"추출된 raw 텍스트: '{raw_text}'")
        print(f"추출된 판례번호: {case_number}")
        return case_number
    else:
        print("[ERROR] 추출된 텍스트가 없습니다.")
        return None


def insert_document_and_get_id(cur, pdf_filename, pdf_url):
    """documents 테이블에 삽입하고 document_id를 RETURNING 받습니다."""

    insert_query = """
                   INSERT INTO documents
                       (file_name, file_path, uploaded_by_user_id, document_scope, status)
                   VALUES ( %s, %s, %s, %s, %s)
                       RETURNING document_id; \
                   """

    try:
        cur.execute(insert_query, (pdf_filename, pdf_url, 1, "precedent", "ready"))
        document_id = cur.fetchone()[0]
        return document_id
    except Exception as e:
        print(f"[ERROR] Documents 테이블에 삽입 실패: {e}")
        return None


# ----------------------------------------------------------------------
# Helper 3: HTML 본문 추출 및 마크다운 구조화
# ----------------------------------------------------------------------
def get_header_keys():
    # 💡 수정된 SYMBOL_PREFIXES 정의
    # 아라비아 숫자: 1부터 9까지 (f-string 사용)
    # 1. 아라비아 숫자 (1. ~ 9., 1) ~ 9))
    # numeric_dots = [ f'{i}.' for i in range(1, 10)]
    numeric_paren = [f"{i})" for i in range(1, 10)]

    # # 2. 한글 순번 (가. ~ 하., 가) ~ 하))
    # hangul_dots = [f'{chr(i)}.' for i in range(ord('가'), ord('하') + 1)]
    # hangul_paren = [f'{chr(i)})' for i in range(ord('가'), ord('하') + 1)]

    # 3. 원문자 순번 (① ~ ⑩, ①. ~ ⑩.)
    circle_number_base = [chr(i) for i in range(0x2460, 0x2469 + 1)]
    circle_number_dots = [f"{c}." for c in circle_number_base]

    # 4. 기타 기호
    other_symbols = ["◇", "☞", "["]
    return list(numeric_paren + circle_number_dots + other_symbols)


def preprocess_precedent_text_to_markdown(text: str) -> str:
    header_keys: list[str] = get_header_keys()
    processed_text = text
    for key in header_keys:
        processed_text = processed_text.replace(key, f"\n## {key.strip()}\n", 1)
    return processed_text.strip()


def split_precedent_markdown_chunks_with_fallback(
    text: str,
    max_chunk_size: int = 500,
    chunk_overlap: int = 50,
    headers_to_split_on=[("##", "Section_Level_2"), ("###", "Section_Level_3")],
) -> list[dict]:
    full_text = re.sub(r"\n{3,}", "\n\n", text)
    print(f"    [청킹할 텍스트] {full_text[:300]}")

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


def get_new_precedent_urls(
    list_url="https://www.scourt.go.kr/portal/news/NewslistAction.work?gubun=4&type=5",
    base_url="https://www.scourt.go.kr",
):
    _, conn, cur = conn_embedding_model()

    if conn is None:
        return []

    # ⭐️ 1. DB에서 마지막 처리 날짜 가져오기 (precedent_date 기준)
    last_precedent_date = None
    try:
        cur.execute("SELECT MAX(precedent_date) FROM precedent_log;")
        result = cur.fetchone()[0]
        conn.close()

        if result:
            last_precedent_date = result
            print(
                f"마지막 처리 날짜: {last_precedent_date.strftime('%Y-%m-%d')} 이후 데이터를 확인합니다."
            )
        else:
            print("처리 이력이 없습니다. 전체 목록을 확인합니다.")
    except Exception as e:
        print(f"[DB 오류] precedent_log 쿼리 실패: {e}")
        conn.close()
        return []

    # 2. 판례 목록 크롤링 및 날짜/링크 필터링
    try:
        response = requests.get(list_url, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"크롤링 오류 발생: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    rows = soup.select("table.tableHor tr")
    all_candidate_urls = []

    for row in rows:
        link = row.select_one("td.tit a")
        date_tag = row.select_one("td:nth-child(4)")

        if link and date_tag and date_tag.text.strip():
            href = link.get("href")
            date_str = date_tag.text.strip()

            try:
                precedent_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                continue

            abs_url = urljoin(base_url, href)

            is_recent_enough = True

            if last_precedent_date:
                if precedent_date <= last_precedent_date:
                    is_recent_enough = False

            if is_recent_enough and "NewsViewAction.work" in abs_url:
                all_candidate_urls.append(abs_url)

    if not all_candidate_urls:
        print("날짜 필터링 후, 크롤링할 신규 URL이 없습니다.")
        return []

    new_urls = list(set(all_candidate_urls))
    print(f"날짜 필터링 후 최종 신규 판례 {len(new_urls)}개 발견. (상세 페이지 URL)")
    return new_urls


def extract_precedent_metadata(
    soup: BeautifulSoup, detail_url: str
) -> Optional[dict[str, Any]]:
    def get_text_after_th(th_text: str) -> str:
        """특정 <th> 태그 뒤의 <td> 텍스트를 안전하게 추출합니다."""
        th = soup.find("th", string=lambda t: t and th_text in t.strip())
        target_td = th.find_next_sibling("td") if th else None
        return target_td.text.strip() if target_td else f"{th_text} 없음"

    try:
        # 1. 메타데이터 추출
        precedent_title = get_text_after_th("제목")
        precedent_date_str = get_text_after_th("작성일")

        # 날짜가 추출되지 않았다면 현재 날짜 사용
        if "없음" in precedent_date_str:
            precedent_date_str = datetime.now().strftime("%Y-%m-%d")

        # PDF URL/파일명 추출 (로그 기록용)
        file_link_tag = soup.find(
            "a", href=lambda href: href and href.lower().endswith(".pdf")
        )
        pdf_href = file_link_tag.get("href") if file_link_tag else detail_url
        pdf_filename = os.path.basename(pdf_href)

        # 판례번호 추출 (td.contArea의 첫 번째 <p> 가정)
        case_num = extract_case_number_from_contarea(soup)  # 외부 함수 호출

        # 2. 본문 텍스트 추출 (raw_text)
        content_div = soup.find("td", class_="contArea")
        # NOTE: 원본 코드의 \n\n 분리자를 유지하여 추출 (효율적)
        raw_text = content_div.get_text("\n\n", strip=True) if content_div else ""

        if not raw_text.strip():
            print("   [SKIP] 추출된 본문 텍스트가 없습니다.")
            return None

        # 3. 데이터 구조 반환
        return {
            "title": precedent_title,
            "date_str": precedent_date_str,
            "pdf_href": pdf_href,
            "pdf_filename": pdf_filename,
            "case_num": case_num,
            "raw_text": raw_text,
        }
    except Exception as e:
        print(f"   [ERROR] 메타데이터 추출 중 오류 발생: {e}")
        return None


def insert_embeddings_and_log_chunks(
    document_id: int,
    texts: list[dict],
    precedent_data: dict[str, Any],
    embeddings: OllamaEmbeddings,
    conn: connection,
    cur: cursor,
) -> int:
    total_chunks = len(texts)
    successful_chunks = 0
    embeded_texts = []
    try:
        # 1. 임베딩 생성
        for i, chunk in enumerate(texts):
            # 💡 수정: chunk['page_content']를 사용하여 텍스트 내용을 먼저 추출
            content = chunk["page_content"]
            embeded_texts.append(content)
        texts = embeded_texts
        vectors = embeddings.embed_documents(texts)
    except Exception as e:
        print(f"   [ERROR] Ollama 임베딩 생성 실패: {e}. 청크 삽입을 건너뜀.")
        return 0

    # 2. Chunk 데이터 삽입 (document_chunks)
    insert_chunk_query = """
                         INSERT INTO document_chunks
                             (document_id, content, embedding, meta)
                         VALUES (%s, %s, %s, %s); \
                         """

    for i, (text, vector) in enumerate(zip(texts, vectors)):
        try:
            # pgvector 형식 문자열 변환
            vector_str = "[" + ",".join(map(str, vector)) + "]"

            # 메타데이터 구성 (기존 precedent_data를 기반으로)
            meta_data_json = {
                "case_num": precedent_data.get("case_num"),
                "source_url": precedent_data["pdf_href"],
                "precedent_title": precedent_data["title"],
                "attached_filename": precedent_data["pdf_filename"],
                "chunk_index": i,
            }

            cur.execute(
                insert_chunk_query,
                (
                    document_id,
                    text,
                    vector_str,
                    json.dumps(meta_data_json, ensure_ascii=False),
                ),
            )
            successful_chunks += 1

        except Exception as e:
            # 요구사항 반영: 청크 삽입 중 오류나면 중단하지 않고 다음 청크로 넘어감
            print(
                f"[WARNING] Chunk {i + 1}/{total_chunks} 삽입 실패 (ID: {document_id}): {e}"
            )
            continue

    return successful_chunks


def process_precedent_data(detail_url: str):
    embeddings, conn, cur = conn_embedding_model()

    if conn is None:
        raise Exception

    # 1. 상세 페이지 접속
    try:
        response = requests.get(detail_url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        print(f"   [ERROR] 상세 페이지 접근/파싱 실패: {e}")
        conn.close()
        raise Exception

    # 2. 메타데이터 및 raw_text 추출 (새 함수 호출)
    precedent_data = extract_precedent_metadata(soup, detail_url)
    if precedent_data is None:
        conn.close()
        return

    # 3. 텍스트 전처리 및 분할
    full_text = preprocess_precedent_text_to_markdown(
        precedent_data["raw_text"]
    )  # 외부 함수 호출
    texts = split_precedent_markdown_chunks_with_fallback(full_text)  # 외부 함수 호출
    # ----------------------------------------------------
    # 💡 수정된 로깅 코드: Dictionary 구조 참조 및 출력 강화
    # ----------------------------------------------------
    print(f"\n--- 청킹 결과 요약 ({len(texts)} chunks) ---")
    for i, chunk_dict in enumerate(texts):
        # 1. 'page_content' 키를 사용하여 텍스트 내용 추출
        content = chunk_dict.get("page_content", "[NO CONTENT]")

        # 2. 'metadata' 키를 사용하여 메타데이터 추출 (JSONB 삽입 전 디버깅)
        metadata = chunk_dict.get("metadata", {})

        # 3. 로그 출력 (내용 앞부분 100자와 메타데이터를 함께 출력)
        print(f"  [Chunk {i + 1}] (Len: {len(content)}): ")
        print(f"    Content Start: '{content[:100].replace('\n', ' ')}...'")
        print(f"    Metadata: {metadata}")

    print("-------------------------------------------\n")
    # 로그 출력
    print(f"\n--- 청킹 결과 요약 ({len(texts)} chunks) ---")
    for i, chunk in enumerate(texts):
        # 💡 수정: chunk['page_content']를 사용하여 텍스트 내용을 먼저 추출
        content = chunk["page_content"]
        print(f"  [Chunk {i + 1}]: '{content[:100].replace('\n', ' ')}...'")
    print("-------------------------------------------\n")

    # 4. Document 테이블에 먼저 삽입 시도 및 ID 획득
    document_id = insert_document_and_get_id(
        cur, precedent_data["pdf_filename"], precedent_data["pdf_href"]
    )

    if document_id is None:
        conn.close()
        return

    # 5. 청크 처리 및 DB 삽입 (새 함수 호출)
    successful_chunks = insert_embeddings_and_log_chunks(
        document_id, texts, precedent_data, embeddings, conn, cur
    )

    # 6. 로그 기록 및 트랜잭션 커밋
    if successful_chunks > 0:
        insert_log_query = """
                           INSERT INTO precedent_log (precedent_url, precedent_date, title)
                           VALUES (%s, %s, %s)
                               ON CONFLICT (precedent_url) DO NOTHING; \
                           """
        try:
            # precedent_date_str을 datetime.date 객체로 변환하여 삽입
            precedent_date = datetime.strptime(
                precedent_data["date_str"], "%Y-%m-%d"
            ).date()
            cur.execute(
                insert_log_query, (detail_url, precedent_date, precedent_data["title"])
            )
        except Exception as e:
            print(f"[ERROR] 로그 기록 실패: {e}")

        conn.commit()
        print(f"[SUCCESS] {successful_chunks} 청크 삽입 및 로그 완료.")
    else:
        conn.rollback()
        print("[WARNING] 청크 삽입 성공 건수 0. 트랜잭션 롤백.")

    conn.close()
    return f"Processed {detail_url}"


# ----------------------------------------------------------------------
# 5. 메인 워크플로우 (update_rag_index)
# ----------------------------------------------------------------------
@celery_app.task(name="update-rag-index-task")
def update_rag_index():
    """
    신규 URL 목록을 가져와 각 URL에 대해 처리 작업을 실행합니다.
    (Celery Worker의 Task가 호출할 수 있는 메인 함수)
    """
    print("\n--- RAG 데이터 최신화 작업 시작 ---")

    url_links = get_new_precedent_urls()

    if not url_links:
        print("신규 판례가 없어 작업을 종료합니다.")
        return

    for url in url_links:
        result = process_precedent_data(url)
        print(f"처리 요약: {result}")

    print("\n--- RAG 데이터 최신화 작업 완료 ---")
    return
