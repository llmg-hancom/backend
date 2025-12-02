from typing import Sequence, Any

from langchain.tools import tool, ToolRuntime
from langchain_postgres import PGEngine, PGVectorStore
from langchain_postgres.v2.indexes import HNSWQueryOptions
from pydantic import BaseModel
from sqlalchemy import Row, RowMapping
from sqlmodel import select

from db.session import async_engine
from models import Document, ChatSpaceDocument, DocumentChunk
from models.document import DocumentScope
from rag.context_manager import get_db_session
from rag.model import embeddings
from datetime import date

pg_engine = PGEngine.from_engine(async_engine)


class Context(BaseModel):
    space_id: int


# 판례 검색을 위한 필터
class SearchFilter(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    case_numbers: list[str] | None = None


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


async def _fetch_target_ids(
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
        results = await session.execute(statement)
        target_doc_ids = results.scalars().all()
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


async def query_in_precedent(
    query: str,
    query_filter: SearchFilter | None = None,
    k: int = 5,
):
    """판례 검색. query_filter가 존재하는 경우 chunk_id로 필터링,
    존재하지 않는 경우 제외된 document_id로 필터링"""
    vector_store = await create_vector_store(40, 64)
    # 검색 조건이 존재하는 경우 chunk id로 필터링
    if query_filter:
        included_chunk_ids = await _fetch_target_ids(
            DocumentScope.precedent, search_filter=query_filter
        )
        search_filter: dict = {"chunk_id": {"$in": included_chunk_ids}}
    # 검색 조건이 없는 경우 성능을 위해 판례가 아닌 범위의 document_id로 필터링
    else:
        excluded_doc_ids = await _fetch_target_ids(DocumentScope.precedent)
        search_filter: dict = {"document_id": {"$nin": excluded_doc_ids}}
    relevant_chunks = await vector_store.asimilarity_search(
        query, k=k, filter=search_filter
    )
    serialized = "\n\n".join(
        f"Source: {doc.metadata}\nContent: {doc.page_content}"
        for doc in relevant_chunks
    )
    return serialized, relevant_chunks


@tool(response_format="content_and_artifact", parse_docstring=True)
async def search_public_law(query: str):
    """
    This tool is designed for RAG in LLMs,
    specifically for searching Korean public laws.

    Args:
        query (str): The search query for public laws.

    """
    relevant_chunks = []
    serialized = ""
    target_doc_ids = await _fetch_target_ids(DocumentScope.public_law)
    if target_doc_ids:
        serialized, relevant_chunks = await query_in_target(query, target_doc_ids)
    return serialized, relevant_chunks


@tool(response_format="content_and_artifact", parse_docstring=True)
async def search_precedent(
    query: str, start_date: date | None = None, end_date: date | None = None
):
    """
    This tool is designed for RAG in LLMs,
    specifically for searching Korean precedents.

    Args:
        query (str): The search query for precedents. This should be a concise and clear question or statement.
        start_date (date | None): Optional. The start date for filtering precedents.
                                  Only precedents from this date onwards will be considered.
        end_date (date | None): Optional. The end date for filtering precedents. Only precedents up to this date will be considered.

    """
    search_filter = SearchFilter(start_date=start_date, end_date=end_date)
    serialized, relevant_chunks = await query_in_precedent(query, search_filter)
    return serialized, relevant_chunks


@tool(response_format="content_and_artifact", parse_docstring=True)
async def search_precedent_by_case_number(query: str, case_numbers: list[str]):
    """
    This tool is designed for RAG in LLMs,
    specifically for searching Korean precedents by its case number(사건번호).

    Args:
        query (str): The search query for precedents. This should be a concise and clear question or statement.
        case_numbers (list[str]): The case numbers (사건번호) to filter precedents by.

    """
    # 사건번호에 공백이 있는 경우 모두 제거
    for case_number in case_numbers:
        case_number.replace(" ", "")
    search_filter = SearchFilter(case_numbers=case_numbers)
    serialized, relevant_chunks = await query_in_precedent(query, search_filter)
    return serialized, relevant_chunks


@tool(response_format="content_and_artifact", parse_docstring=True)
async def search_private_documents(query: str, runtime: ToolRuntime[Context]):
    """
    This tool is designed for RAG in LLMs,
    specifically for searching private document chunks.

    Args:
        query (str): The search query for private documents.
    """
    relevant_chunks = []
    serialized = ""
    target_doc_ids = await _fetch_target_ids(
        DocumentScope.private, runtime.context.space_id
    )
    if target_doc_ids:
        serialized, relevant_chunks = await query_in_target(query, target_doc_ids)
    return serialized, relevant_chunks