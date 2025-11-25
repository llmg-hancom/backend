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


async def _fetch_target_ids(document_scope: DocumentScope, space_id: int | None = None):
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


async def query_excluding_docs(
    query: str, excluded_doc_ids: Sequence[Row[Any] | RowMapping | Any], k: int = 5
):
    vector_store = await create_vector_store(40, 64)
    relevant_chunks = await vector_store.asimilarity_search(
        query, k=k, filter={"document_id": {"$nin": excluded_doc_ids}}
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
async def search_precedent(query: str):
    """
    This tool is designed for RAG in LLMs,
    specifically for searching Korean precedents.

    Args:
        query (str): The search query for precedents.

    """
    relevant_chunks = []
    serialized = ""
    target_doc_ids = await _fetch_target_ids(DocumentScope.precedent)
    if target_doc_ids:
        serialized, relevant_chunks = await query_excluding_docs(query, target_doc_ids)
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