from typing import Optional, Sequence, Any

from langchain_core.tools import tool
from langchain_postgres import PGEngine, PGVectorStore
from sqlalchemy import Row, RowMapping
from sqlmodel import select

from db.session import async_engine
from models import Document, ChatSpaceDocument
from models.document import DocumentScope
from rag.context_manager import get_db_session
from rag.model import embeddings

pg_engine = PGEngine.from_engine(async_engine)


async def create_vector_store() -> PGVectorStore:
    vector_store = await PGVectorStore.create(
        engine=pg_engine,
        embedding_service=embeddings,
        table_name="document_chunks",
        id_column="chunk_id",
        metadata_columns=["document_id", "created_at"],
        metadata_json_column="meta",
    )
    return vector_store


async def _search_target_ids(
    document_scope: DocumentScope, space_id: Optional[int] = None
):
    async with get_db_session() as session:
        match document_scope:
            case DocumentScope.public_law:
                statement = select(Document.document_id).where(
                    Document.document_scope == DocumentScope.public_law
                )
            case DocumentScope.precedent:
                statement = select(Document.document_id).where(
                    Document.document_scope == DocumentScope.precedent
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


@tool(response_format="content_and_artifact")
async def search_public_law(query: str):
    """
    This tool is designed for RAG in LLMs,
    specifically for searching Korean public laws.

    Args:
        query (str): The search query for public laws.

    """
    relevant_chunks = []
    serialized = ""
    target_doc_ids = await _search_target_ids(DocumentScope.public_law)
    if target_doc_ids:
        serialized, relevant_chunks = await query_in_target(query, target_doc_ids)
    return serialized, relevant_chunks


@tool(response_format="content_and_artifact")
async def search_precedent(query: str):
    """
    This tool is designed for RAG in LLMs,
    specifically for searching Korean precedents.

    Args:
        query (str): The search query for precedents.

    """
    relevant_chunks = []
    serialized = ""
    target_doc_ids = await _search_target_ids(DocumentScope.precedent)
    if target_doc_ids:
        serialized, relevant_chunks = await query_in_target(query, target_doc_ids)
    return serialized, relevant_chunks


@tool(response_format="content_and_artifact")
async def search_private_documents(space_id: int, query: str):
    """
    This tool is designed for RAG in LLMs,
    specifically for searching private document chunks.

    Args:
        space_id (int): The ID of the chat space.
        query (str): The search query private documents.

    """
    relevant_chunks = []
    serialized = ""
    target_doc_ids = await _search_target_ids(DocumentScope.private, space_id)
    if target_doc_ids:
        serialized, relevant_chunks = await query_in_target(query, target_doc_ids)
    return serialized, relevant_chunks