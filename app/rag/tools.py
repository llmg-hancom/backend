from typing import Sequence, Any

from langchain.tools import tool, ToolRuntime
from langchain_postgres import PGEngine, PGVectorStore
from langchain_postgres.v2.indexes import HNSWQueryOptions
from pydantic import BaseModel
from sqlalchemy import Row, RowMapping
from sqlmodel import select

from db.session import async_engine
from models import Document, ChatSpaceDocument
from models.document import DocumentScope
from rag.context_manager import get_db_session
from rag.model import embeddings
from datetime import date

pg_engine = PGEngine.from_engine(async_engine)


class Context(BaseModel):
    space_id: int


async def create_vector_store(fetch_k: int = 20, ef_search: int = 40) -> PGVectorStore:
    vector_store = await PGVectorStore.create(
        engine=pg_engine,
        embedding_service=embeddings,
        table_name="document_chunks",
        id_column="chunk_id",
        metadata_columns=["document_id", "created_at"],
        metadata_json_column="meta",
        fetch_k=fetch_k,
        index_query_options=HNSWQueryOptions(ef_search=ef_search),
    )
    return vector_store


async def _fetch_target_ids(
    document_scope: DocumentScope,
    space_id: int | None = None,
):
    async with get_db_session() as session:
        match document_scope:
            case DocumentScope.public_law:
                statement = select(Document.document_id).where(
                    Document.document_scope == DocumentScope.public_law
                )
            case DocumentScope.precedent:
                statement = select(Document.document_id).where(
                    Document.document_scope != DocumentScope.precedent
                )
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
    k: int = 5,
    start_date: date | None = None,
    end_date: date | None = None,
    case_number: str | None = None,
):
    vector_store = await create_vector_store(40, 64)
    excluded_doc_ids = await _fetch_target_ids(DocumentScope.precedent)
    search_filter: dict = {"document_id": {"$nin": excluded_doc_ids}}
    if start_date:
        search_filter["사건번호"] = {"$gte": start_date.strftime("%Y%m%d")}
    if end_date:
        search_filter.setdefault("사건번호", {})["$lte"] = end_date.strftime("%Y%m%d")
    if case_number:
        search_filter["선고일자"] = {"$eq": case_number}
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
    serialized, relevant_chunks = await query_in_precedent(
        query, start_date=start_date, end_date=end_date
    )
    return serialized, relevant_chunks


@tool(response_format="content_and_artifact", parse_docstring=True)
async def search_precedent_by_case_number(query: str, case_number: str):
    """
    This tool is designed for RAG in LLMs,
    specifically for searching Korean precedents by its case number(사건번호).

    Args:
        query (str): The search query for precedents. This should be a concise and clear question or statement.
        case_number (str): The case number (사건번호) to filter precedents by.

    """
    serialized, relevant_chunks = await query_in_precedent(
        query, case_number=case_number
    )
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