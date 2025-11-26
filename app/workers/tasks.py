import json
import re
import uuid
from contextlib import contextmanager
from pathlib import Path
import shutil
import time
from typing import Literal

from langchain.messages import HumanMessage, SystemMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field, field_validator

from rag.model import llm
from celery.utils.log import get_task_logger


# from models.document_chunk import DocumentChunk
# from rag.embedding import embed_texts  # (BGE-m3-ko 1024d)
from rag.cleaning import (
    clean_common_noise,
    clean_rag_text,
    process_html_with_tables,
    normalize_regex_pattern,
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


# LLM 문서 구조 분석을 위한 structured output
class SeparatorItem(BaseModel):
    pattern: str = Field(
        description="A raw Python regular expression string compatible with the `re` module. Do NOT enclose in forward slashes (`/`). Ensure backslashes are properly escaped (e.g., '\\n\\n', '(?<=\\.)\\s')."
    )
    description: str = Field(
        description="The rationale for choosing this separator and its specific role in the hierarchy (e.g., 'Primary splitter for distinct chapters' or 'Splits paragraphs')."
    )

    @field_validator("pattern")
    @classmethod
    def validate_regex(cls, v):
        try:
            re.compile(v)
        except re.error:
            raise ValueError(f"Invalid Python regex pattern: {v}")
        return v


class DocumentAnalysis(BaseModel):
    """
    Analysis result containing the document's structure, metadata, and splitting strategy.
    """

    is_structured: bool = Field(
        description="True if the document exhibits a clear hierarchical structure (e.g., headers, distinct sections); False if it is unstructured text."
    )
    suggested_separators: list[SeparatorItem] = Field(
        description="A list of recommended Regex delimiters to split the document, ordered by hierarchy from largest unit (e.g., Chapters) to smallest unit (e.g., Sentences)."
    )
    title: str = Field(
        description="The document title. If not explicitly present in the text, generate a concise and descriptive title based on the content."
    )
    language: str = Field(
        description="The ISO 639-1 language code representing the main language of the document (e.g., 'en', 'ko', 'ja')."
    )
    keywords: list[str] = Field(
        description="A list of up to 5 key terms relevant to the document content, optimized for search indexing."
    )
    summary: str = Field(
        description="A single-sentence summary acting as a preview for the user. Use the same language as the original."
    )
    category: str = Field(
        description="The classification of the document type (e.g., 'Report', 'Contract', 'Manual', 'Article', 'Memo')."
    )


@celery_app.task(name="chunk-document-task", bind=True, max_retries=3)
def chunk_document(self, s3_path: str, doc_id: int) -> str:
    logger.info(f"[TASK_START] 문서 청킹 시작: (doc_id: {doc_id})")
    # 임시 디렉토리 생성
    file_dir = DOWNLOAD_DIR / f"{doc_id}_{time.time()}"
    file_dir.mkdir(parents=True)
    try:
        local_path = _download_from_s3(s3_path, file_dir)
        with open(local_path, "r", encoding="utf-8") as f:
            full_text = f.read()
        if len(full_text) > 3000:
            text_head = full_text[:2000]
        else:
            text_head = full_text
        model = llm.with_structured_output(DocumentAnalysis)
        messages = [
            SystemMessage(
                """
                You are an expert in document structure analysis and NLP.
                Your task is to analyze the beginning (head) of a provided document to determine the most efficient chunking strategy for a RAG system.

                Analyze the layout, headers, and formatting patterns.
                Based on this analysis, populate the output schema, paying special attention to the `suggested_separators` field.
                
                ### 1. Summary Guidelines
                - Generate a `one-sentence, short summary` of the **informational content**, not the visual layout. Use the same natural language as the document.
                - BAD: "The document contains lists and headers."
                - GOOD: "This document outlines the Ministry's 2025 strategic plan for digital platform government."
                
                ### 2. Separator (Regex) Guidelines for TextSplitters
                1. Identify the hierarchical structure (e.g., Main Chapters > Sections > Paragraphs).
                2. Propose Python-compatible Regular Expressions (regex) that can split the text effectively.
                3. Order the separators by hierarchy, from the largest logical unit (e.g., Chapter breaks) to the smallest (e.g., Sentence endings).
                4. Ensure regex patterns are raw strings ready for Python's `re` module (e.g., avoid unnecessary forward slashes like `/pattern/`).
                """
            ),
            HumanMessage(f"Here is the beginning of the document:\n\n{text_head}"),
        ]
        logger.info(f"문서 구조 분석 중... : (doc_id: {doc_id})")
        result: DocumentAnalysis = model.invoke(messages)
        logger.info(f"문서 구조 분석 완료: (doc_id: {doc_id})")
        if result.is_structured:
            raw_patterns = [item.pattern for item in result.suggested_separators]
            clean_patterns = [normalize_regex_pattern(p) for p in raw_patterns]
        else:
            clean_patterns = []
        final_separators = clean_patterns + ["\n\n", "\n", " ", ""]
        for regex in final_separators:
            logger.info(regex)
        splitter = RecursiveCharacterTextSplitter(
            separators=final_separators,
            chunk_size=500,
            chunk_overlap=50,
            is_separator_regex=True,
        )
        # 4. 문서 청킹 (Raw Chunks 생성)
        raw_chunks = splitter.create_documents([full_text])

        # 5. [핵심] 모든 청크에 메타데이터 일괄 주입
        # Pydantic 모델을 dict로 변환하되, '청킹 전략' 필드는 메타데이터에 넣을 필요 없으므로 제외
        metadata_to_inject = result.model_dump(
            exclude={"suggested_separators", "is_structured"}
        )

        chunks: list[dict] = []
        for chunk in raw_chunks:
            # 기존 메타데이터(있다면)에 분석된 메타데이터 병합
            chunk.metadata.update(metadata_to_inject)
            chunks.append(
                {"page_content": chunk.page_content, "metadata": chunk.metadata}
            )
        json_path = local_path.with_suffix(".json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)
        json_s3_path = _upload_tmp_s3(json_path, ext="json")
        logger.info(f"[TASK_SUCCESS] 문서 청킹 완료: (doc_id: {doc_id})")
        return str(json_s3_path)
    except FileNotFoundError as e:
        raise self.retry(exc=e, countdown=2)
    except Exception as e:
        logger.error(f"[TASK_FAILED] 문서 청킹 실패: (doc_id: {doc_id}) - {e}")
        raise e
    finally:
        _cleanup_temp_dir(file_dir)
