from datetime import date
from enum import StrEnum
from typing import Sequence, Any

from langchain_postgres import PGEngine, PGVectorStore
from langchain_postgres.v2.indexes import HNSWQueryOptions
from pydantic import BaseModel
from sqlalchemy import Row, RowMapping, text

from langchain_core.documents import Document as LCDocument
from sqlmodel import select

from db.session import async_engine
from models import DocumentChunk, ChatSpaceDocument
from models.document import DocumentScope, Document
from rag.context_manager import get_db_session
from rag.model import embeddings

pg_engine = PGEngine.from_engine(async_engine)


async def create_vector_store(fetch_k: int = 20, ef_search: int = 40) -> PGVectorStore:
    vector_store = await PGVectorStore.create(
        engine=pg_engine,
        embedding_service=embeddings,
        table_name="document_chunks",
        id_column="chunk_id",
        metadata_columns=["document_id"],
        metadata_json_column="meta",
        fetch_k=fetch_k,
        index_query_options=HNSWQueryOptions(ef_search=ef_search),
    )
    return vector_store


class LawCategory(StrEnum):
    civil = "민법(법률)"
    civil_procedure = "민사소송법(법률)"
    criminal = "형법(법률)"
    criminal_procedure = "형사소송법(법률)"
    labor = "근로기준법(법률)"
    minimal_wage = "최저임금법(법률)"
    personal_information = "개인정보 보호법(법률)"
    occupational_safety = "산업안전보건법(법률)"
    framework_act = "행정기본법(법률)"
    framework_procedure = "행정소송법(법률)"
    administrative_appeals = "행정심판법(법률)"
    constitutional_court = "헌법재판소법(법률)"
    pension = "국민연금법(법률)"
    health_insurance = "국민건강보험법(법률)"
    family = "가족관계의 등록 등에 관한 법률(법률)"


# 판례 검색을 위한 필터
class SearchFilter(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    case_numbers: list[str] | None = None


def format_doc(doc: LCDocument, keys: list[str]) -> str:
    """llm에게 줄 정보 제한 및 추출"""

    # 2. 값이 있는 경우에만 "키: 값" 문자열 생성 (None이나 빈 문자열은 제외)
    meta_parts = [
        f"'{k}': {v}"
        for k in keys
        if (v := doc.metadata.get(k))  # 값이 존재하고(None 아님) 빈 문자열도 아닌 경우
    ]

    # 3. 메타데이터와 본문 결합
    meta_str = ", ".join(meta_parts)
    return f"Source: {meta_str}\nContent: {doc.page_content}"


async def fetch_target_ids(
    document_scope: DocumentScope,
    space_id: int | None = None,
    search_filter: SearchFilter | None = None,
):
    """query 검색 범위 설정. 법령, 개인 문서의 경우 항상 해당하는 document_id 반환.
    판례의 경우 search_filter가 존재하면 해당 조건을 만족하는 chunk_id 반환,
    search_filter가 존재하지 않으면 판례가 **아닌** document_id 반환."""
    async with get_db_session() as session:
        match document_scope:
            # 법령 검색의 경우 법령인 document id를 반환
            case DocumentScope.public_law:
                statement = select(Document.document_id).where(
                    Document.document_scope == DocumentScope.public_law
                )
            # 판례 검색
            case DocumentScope.precedent:
                # search_filter가 존재하는 경우 범위 내 chunk_id 반환
                if search_filter:
                    statement = select(DocumentChunk.chunk_id)
                    if search_filter.start_date:
                        statement = statement.where(
                            DocumentChunk.meta["선고일자"].astext
                            >= search_filter.start_date.strftime("%Y%m%d")
                        )
                    if search_filter.end_date:
                        statement = statement.where(
                            DocumentChunk.meta["선고일자"].astext
                            <= search_filter.end_date.strftime("%Y%m%d")
                        )
                    if search_filter.case_numbers:
                        statement = statement.where(
                            DocumentChunk.meta["사건번호"].astext.in_(
                                search_filter.case_numbers
                            )
                        )
                # search_filter가 존재하지 않는 경우 판례가 **아닌** 범위의 document_id 반환
                else:
                    statement = select(Document.document_id).where(
                        Document.document_scope != DocumentScope.precedent
                    )
            # 개인 문서 검색의 경우 space_id에 속한 document_id 반환
            case DocumentScope.private:
                statement = select(ChatSpaceDocument.document_id).where(
                    ChatSpaceDocument.space_id == space_id
                )
        results = await session.exec(statement)
        target_doc_ids = results.all()
    return target_doc_ids


async def query_in_target(
    query: str, target_doc_ids: Sequence[Row[Any] | RowMapping | Any], k: int = 5
):
    """특정 document_id 범위 내에서 검색"""
    vector_store = await create_vector_store()
    relevant_chunks = await vector_store.asimilarity_search(
        query, k=k, filter={"document_id": {"$in": target_doc_ids}}
    )
    serialized = "\n\n".join(
        f"Source: {doc.metadata}\nContent: {doc.page_content}"
        for doc in relevant_chunks
    )
    return serialized, relevant_chunks


PRECEDENT_KEYS = [
    "사건종류명",
    "선고",
    "법원명",
    "사건명",
    "섹션명",
    "사건번호",
    "선고일자",
    "참조조문",
]


async def query_in_precedent(
    query: str,
    query_filter: SearchFilter | None = None,
    k: int = 5,
) -> tuple[str, list[LCDocument]]:
    """판례 검색. query_filter가 존재하는 경우 chunk_id로 필터링,
    존재하지 않는 경우 제외된 document_id로 필터링"""
    vector_store = await create_vector_store(40, 64)
    # 검색 조건이 존재하는 경우 chunk id로 필터링
    if query_filter:
        included_chunk_ids = await fetch_target_ids(
            DocumentScope.precedent, search_filter=query_filter
        )
        search_filter: dict = {"chunk_id": {"$in": included_chunk_ids}}
    # 검색 조건이 없는 경우 성능을 위해 판례가 아닌 범위의 document_id로 필터링
    else:
        excluded_doc_ids = await fetch_target_ids(DocumentScope.precedent)
        search_filter: dict = {"document_id": {"$nin": excluded_doc_ids}}
    relevant_chunks: list[LCDocument] = await vector_store.asimilarity_search(
        query, k=k, filter=search_filter
    )
    serialized = "\n\n".join(format_doc(doc, PRECEDENT_KEYS) for doc in relevant_chunks)
    return serialized, relevant_chunks


LAW_KEYS = ["법령명", "조", "항", "호"]


async def find_law_by_article(
    law_type: LawCategory, article: int
) -> tuple[str, list[LCDocument]]:
    """법령을 법령명과 조 번호로 검색."""
    serialized = ""
    relevant_chunks = []
    async with get_db_session() as session:
        statement = (
            select(DocumentChunk)
            .where(DocumentChunk.meta["법령명"].astext == str(law_type))
            .where(
                text(f"(SUBSTRING(meta ->> '조' FROM '제([0-9]+)조')::INT) = {article}")
            )
        )
        results = await session.exec(statement)
        raw_chunks = results.all()
        # TODO: 법령 타입/ 조로 검색 개발 중
        relevant_chunks = []
        for chunk in raw_chunks:
            md = chunk.meta
            relevant_chunks.append(
                LCDocument(page_content=chunk.content, metadata=chunk.meta)
            )
        serialized = "\n\n".join(format_doc(doc, LAW_KEYS) for doc in relevant_chunks)
    return serialized, relevant_chunks

