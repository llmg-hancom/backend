from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any, Optional

from bs4 import BeautifulSoup
import requests
from requests.compat import urljoin
from celery.utils.log import get_task_logger
from sqlalchemy import func
from sqlmodel import Session, select

from core.config import settings
from db.session import engine
from models.document import Document, DocumentScope, DocumentStatus
from models.document_chunk import DocumentChunk
from models.precedent_log import PrecedentLog
from workers.celery_app import celery_app

from tqdm import tqdm
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)
from langchain_ollama import OllamaEmbeddings

logger = get_task_logger(__name__)


# --- DB 세션 관리를 위한 컨텍스트 매니저 ---
@contextmanager
def get_db_session():
    """Provide a transactional scope around a series of operations."""
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception as e:
            logger.error(f"DB Session error, rolling back: {e}")
            raise


# --- 임베딩 모델 초기화 ---
def init_embedding_model():
    """
    임베딩 모델 클라이언트를 초기화합니다.
    """
    OLLAMA_BASE_URL = settings.OLLAMA_BASE_URL
    OLLAMA_MODEL = "bge-m3:567m"  # or another model
    embeddings = OllamaEmbeddings(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL)
    logger.info(
        f"[EMBED] Ollama 임베딩 모델 '{OLLAMA_MODEL}' 초기화 완료. (URL: {OLLAMA_BASE_URL})"
    )
    return embeddings


# --- 텍스트 처리 및 분할 유틸리티 (기존 코드 유지) ---
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
    recursive_splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""],
        length_function=len,
    )
    final_chunks = []
    for doc in first_split_documents:
        if len(doc.page_content) > max_chunk_size:
            second_split_documents = recursive_splitter.create_documents(
                [doc.page_content]
            )
            for sub_doc in second_split_documents:
                sub_doc.metadata.update(doc.metadata)
                final_chunks.append(
                    {"page_content": sub_doc.page_content, "metadata": sub_doc.metadata}
                )
        else:
            final_chunks.append(
                {"page_content": doc.page_content, "metadata": doc.metadata}
            )
    return final_chunks


# --- JSON 파일 기반 판례 처리 (리팩토링) ---
@celery_app.task(name="process_json_precedents")
def process_json_precedents(target_directory, file_name):
    file_path = Path(target_directory) / file_name
    if not file_path.exists():
        logger.error(f"[EMBED] 파일을 찾을 수 없습니다: {file_path}")
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data_list = json.load(f)
        logger.info(f"[EMBED] 총 {len(data_list)}개 항목 로드 완료.")
    except Exception as e:
        logger.error(f"[EMBED] JSON 로드 실패: {e}")
        return

    embeddings = init_embedding_model()
    uploaded_chunks_count = 0

    for item_data in tqdm(data_list, desc="Processing and Inserting from JSON"):
        try:
            with get_db_session() as session:
                # 1. Document 생성
                file_name_str = item_data.get(
                    "사건번호", f"id_{item_data.get('판례정보일련번호', 'unknown')}"
                )
                new_doc = Document(
                    file_name=file_name_str,
                    uploaded_by_user_id=1,  # 시스템 유저 ID 가정
                    document_scope=DocumentScope.precedent,
                    status=DocumentStatus.processing,
                )
                session.add(new_doc)
                session.flush()  # ID를 할당받기 위해 flush

                # 2. 텍스트 추출 및 분할
                full_text = item_data.pop("전문", None)
                if not full_text:
                    logger.warning(
                        f"'{file_name_str}' 항목에 '전문' 키가 없어 건너뜁니다."
                    )
                    new_doc.status = DocumentStatus.error
                    session.add(new_doc)
                    continue

                markdown_text = preprocess_text_to_markdown(
                    full_text, JUDGMENT_HEADER_KEYS
                )
                chunks = split_markdown_chunks_with_fallback(
                    text=markdown_text, max_chunk_size=1000
                )

                # 3. 각 청크 임베딩 및 DocumentChunk 생성
                chunk_contents = [chunk["page_content"] for chunk in chunks]
                if not chunk_contents:
                    new_doc.status = DocumentStatus.error
                    session.add(new_doc)
                    continue

                vectors = embeddings.embed_documents(chunk_contents)
                base_metadata = item_data.copy()

                for i, chunk_data in enumerate(chunks):
                    combined_metadata = base_metadata.copy()
                    combined_metadata.update(chunk_data["metadata"])

                    chunk_obj = DocumentChunk(
                        document_id=new_doc.document_id,
                        content=chunk_contents[i],
                        embedding=vectors[i],
                        meta=combined_metadata,
                    )
                    session.add(chunk_obj)
                    uploaded_chunks_count += 1

                new_doc.status = DocumentStatus.ready
                session.add(new_doc)

        except Exception as e:
            logger.error(
                f"\n[EMBED] 항목 처리 실패 (사건번호: {item_data.get('사건번호', 'N/A')}) 상세: {e}"
            )
            continue  # 다음 항목으로 넘어감

    logger.info(f"\n[완료] 총 {uploaded_chunks_count}개의 청크가 DB에 삽입되었습니다.")


# --- 웹 크롤링 기반 판례 처리 (리팩토링) ---


def get_new_precedent_urls(
    list_url="https://www.scourt.go.kr/portal/news/NewslistAction.work?gubun=4&type=5",
    base_url="https://www.scourt.go.kr",
):
    last_precedent_date = None
    try:
        with get_db_session() as session:
            result = session.exec(
                select(func.max(PrecedentLog.precedent_date))
            ).one_or_none()
            if result:
                last_precedent_date = result
                logger.info(
                    f"마지막 처리 날짜: {last_precedent_date.strftime('%Y-%m-%d')} 이후 데이터를 확인합니다."
                )
            else:
                logger.info("처리 이력이 없습니다. 전체 목록을 확인합니다.")
    except Exception as e:
        logger.error(f"[DB 오류] precedent_log 쿼리 실패: {e}")
        return []

    try:
        response = requests.get(list_url, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"크롤링 오류 발생: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    rows = soup.select("table.tableHor tr")
    new_urls = []

    for row in rows:
        link = row.select_one("td.tit a")
        date_tag = row.select_one("td:nth-child(4)")

        if link and date_tag and (date_str := date_tag.text.strip()):
            try:
                precedent_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                if last_precedent_date and precedent_date <= last_precedent_date:
                    continue

                href = link.get("href")
                if "NewsViewAction.work" in href:
                    new_urls.append(urljoin(base_url, href))
            except ValueError:
                continue

    unique_urls = sorted(list(set(new_urls)))
    logger.info(f"최종 신규 판례 {len(unique_urls)}개 발견.")
    return unique_urls


def extract_precedent_metadata(
    soup: BeautifulSoup, detail_url: str
) -> Optional[dict[str, Any]]:
    def get_text_after_th(th_text: str) -> str:
        th = soup.find("th", string=lambda t: t and th_text in t.strip())
        td = th.find_next_sibling("td") if th else None
        return td.text.strip() if td else ""

    try:
        title = get_text_after_th("제목")
        date_str = get_text_after_th("작성일") or datetime.now().strftime("%Y-%m-%d")

        file_link = soup.find(
            "a", href=lambda href: href and href.lower().endswith(".pdf")
        )
        pdf_href = file_link.get("href") if file_link else detail_url

        cont_area = soup.select_one("td.contArea")
        raw_text = cont_area.get_text("\n\n", strip=True) if cont_area else ""

        if not raw_text.strip():
            logger.info("   [SKIP] 추출된 본문 텍스트가 없습니다.")
            return None

        first_p = cont_area.find("p")
        case_num = first_p.get_text(strip=True).split()[0] if first_p else "Unknown"

        return {
            "title": title,
            "date_str": date_str,
            "pdf_href": pdf_href,
            "pdf_filename": os.path.basename(pdf_href),
            "case_num": case_num,
            "raw_text": raw_text,
        }
    except Exception as e:
        logger.error(f"    메타데이터 추출 중 오류 발생: {e}")
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


def process_precedent_url(detail_url: str, embeddings: OllamaEmbeddings):
    try:
        response = requests.get(detail_url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        logger.error(f"상세 페이지 접근/파싱 실패 ({detail_url}): {e}")
        return

    precedent_data = extract_precedent_metadata(soup, detail_url)
    if not precedent_data:
        return

    try:
        with get_db_session() as session:
            # 중복 처리 확인
            existing_log = session.exec(
                select(PrecedentLog).where(PrecedentLog.precedent_url == detail_url)
            ).first()
            if existing_log:
                logger.info(f"이미 처리된 URL입니다: {detail_url}")
                return

            # 1. Document 생성
            new_doc = Document(
                file_name=precedent_data["pdf_filename"],
                file_path=precedent_data["pdf_href"],
                uploaded_by_user_id=1,  # 시스템 유저
                document_scope=DocumentScope.precedent,
                status=DocumentStatus.processing,
            )
            session.add(new_doc)
            session.flush()

            # 2. 텍스트 분할
            markdown_text = preprocess_precedent_text_to_markdown(
                precedent_data["raw_text"]
            )
            chunks = split_markdown_chunks_with_fallback(markdown_text)

            if not chunks:
                new_doc.status = DocumentStatus.error
                logger.warning("청킹 결과가 없어 문서를 error 상태로 저장합니다.")
                return

            # 3. 임베딩 및 DocumentChunk 저장
            chunk_contents = [chunk["page_content"] for chunk in chunks]
            vectors = embeddings.embed_documents(chunk_contents)

            for i, chunk_data in enumerate(chunks):
                meta = {
                    "case_num": precedent_data.get("case_num"),
                    "source_url": precedent_data["pdf_href"],
                    "precedent_title": precedent_data["title"],
                    "chunk_index": i,
                }
                meta.update(chunk_data.get("metadata", {}))

                chunk_obj = DocumentChunk(
                    document_id=new_doc.document_id,
                    content=chunk_contents[i],
                    embedding=vectors[i],
                    meta=meta,
                )
                session.add(chunk_obj)

            # 4. 처리 로그 기록 및 문서 상태 업데이트
            precedent_date = datetime.strptime(
                precedent_data["date_str"], "%Y-%m-%d"
            ).date()
            new_log = PrecedentLog(
                precedent_url=detail_url,
                precedent_date=precedent_date,
                title=precedent_data["title"],
            )
            session.add(new_log)

            new_doc.status = DocumentStatus.ready
            logger.info(f"{len(chunks)}개 청크 삽입 및 로그 완료: {detail_url}")

    except Exception as e:
        logger.error(f"URL 처리 실패 ({detail_url}): {e}")


@celery_app.task(name="update-rag-index-task")
def update_rag_index():
    """
    신규 판례를 크롤링하여 처리하고 데이터베이스에 저장합니다.
    """
    logger.info("\n[TASK_START] --- RAG 데이터 최신화 작업 시작 ---")
    
    new_urls = get_new_precedent_urls()
    if not new_urls:
        logger.info("신규 판례가 없어 작업을 종료합니다.")
        return

    embeddings = init_embedding_model()
    for url in new_urls:
        process_precedent_url(url, embeddings)

    logger.info("\n[TASK_SUCCESS]--- RAG 데이터 최신화 작업 완료 ---")
