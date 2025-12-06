import html
from contextlib import contextmanager
import json
from pathlib import Path
import re
import time

from celery.utils.log import get_task_logger
from langchain.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field, field_validator

from core.config import settings

# from models.document_chunk import DocumentChunk
# from rag.embedding import embed_texts  # (BGE-m3-ko 1024d)
from rag.cleaning import (
    normalize_regex_pattern,
)
from sqlmodel import Session
from workers.celery_app import celery_app
from workers.tasks import cleanup_temp_dir, download_from_s3, upload_tmp_s3

from db.session import engine


logger = get_task_logger(__name__)


@contextmanager
def get_db_session():
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            raise


llm = ChatOllama(
    model="gpt-oss:latest",
    validate_model_on_init=True,
    base_url=settings.OLLAMA_BASE_URL,
    keep_alive="4h",
    temperature=0,
)

# 임시 파일 저장 경로
DOWNLOAD_DIR = Path("/tmp/hwp-tasks")

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
        description="A list of up to 5 key terms relevant to the document content, optimized for search indexing.",
        max_length=5,
    )
    summary: str = Field(
        description="A single-sentence summary acting as a preview for the user. Always use the same language as the original document."
    )
    category: str = Field(
        description="The classification of the document type (e.g., 'Report', 'Contract', 'Manual', 'Article', 'Memo')."
    )


@celery_app.task(name="chunk-user-document-task", bind=True, max_retries=3)
def chunk_user_document(self, s3_path: str, doc_id: int) -> str:
    logger.info(f"[TASK_START] 문서 청킹 시작: (doc_id: {doc_id})")
    # 임시 디렉토리 생성
    file_dir = DOWNLOAD_DIR / f"{doc_id}_{time.time()}"
    file_dir.mkdir(parents=True)
    try:
        local_path = download_from_s3(s3_path, file_dir)
        with open(local_path, "r", encoding="utf-8") as f:
            full_text = f.read()
        full_text = html.unescape(full_text)
        if len(full_text) > 3000:
            text_head = full_text[:2000]
        else:
            text_head = full_text
        model = llm.with_structured_output(DocumentAnalysis)
        messages = [
            SystemMessage(
                """
                You are an expert in document structure analysis and NLP.
                Your task is to analyze the beginning (head) of a provided document to determine the most efficient
                chunking strategy for a RAG system.

                Analyze the layout, headers, and formatting patterns.
                Based on this analysis, populate the output schema, paying special attention to the
                `suggested_separators` field.

                ### 1. Summary Guidelines

                - Generate a `one-sentence, short summary` of the **informational content**, not the visual layout.
                  For summary, use the same language as the document. (e.g. Summarize in Korean if the original document is in Korean.)
                - BAD: "The document contains lists and headers."
                - GOOD: "This document outlines the Ministry's 2025 strategic plan for digital platform government."

                ### 2. Separator (Regex) Guidelines for TextSplitters

                1. Identify the hierarchical structure (e.g., Main Chapters > Sections > Paragraphs).
                2. Propose Python-compatible Regular Expressions (regex) that can split the text effectively.
                3. Order the separators by hierarchy, from the largest logical unit (e.g., Chapter breaks) to the
                   smallest (e.g., Sentence endings).
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
        final_separators = clean_patterns + [r"\n\n", r"\n", " ", ""]
        for regex in final_separators:
            logger.info(regex)
        table_pattern = r"<\s*table_data\s*>.*?<\s*/\s*table_data\s*>"
        tables = re.findall(table_pattern, full_text, flags=re.DOTALL)

        masked_text = full_text
        for i, table_content in enumerate(tables):
            # 유니크한 마커로 대체 (정규식이 절대 건드리지 않을 문자열)
            placeholder = f"__PROTECTED_TABLE_{i}__"
            masked_text = masked_text.replace(table_content, placeholder)

        splitter = RecursiveCharacterTextSplitter(
            separators=final_separators,
            chunk_size=800,
            chunk_overlap=200,
            is_separator_regex=True,
            keep_separator=True,
        )
        # 4. 문서 청킹 (Raw Chunks 생성)
        raw_chunks = splitter.create_documents([masked_text])

        # 5. [핵심] 모든 청크에 메타데이터 일괄 주입
        # Pydantic 모델을 dict로 변환하되, '청킹 전략' 필드는 메타데이터에 넣을 필요 없으므로 제외
        metadata_to_inject = result.model_dump(
            exclude={"suggested_separators", "is_structured"}
        )

        chunks: list[dict] = []
        for chunk in raw_chunks:
            if "__PROTECTED_TABLE_" in chunk.page_content:
                for i, table_content in enumerate(tables):
                    placeholder = f"__PROTECTED_TABLE_{i}__"
                    if placeholder in chunk.page_content:
                        chunk.page_content = chunk.page_content.replace(
                            placeholder, table_content
                        )
            # 기존 메타데이터(있다면)에 분석된 메타데이터 병합
            chunk.metadata.update(metadata_to_inject)
            chunks.append(
                {"page_content": chunk.page_content, "metadata": chunk.metadata}
            )
        json_path = local_path.with_suffix(".json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)
        json_s3_path = upload_tmp_s3(json_path, ext="json")
        logger.info(f"[TASK_SUCCESS] 문서 청킹 완료: (doc_id: {doc_id})")
        return str(json_s3_path)
    except FileNotFoundError as e:
        raise self.retry(exc=e, countdown=2)
    except Exception as e:
        logger.error(f"[TASK_FAILED] 문서 청킹 실패: (doc_id: {doc_id}) - {e}")
        raise e
    finally:
        cleanup_temp_dir(file_dir)