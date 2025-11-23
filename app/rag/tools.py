from langchain_core.tools import tool
from langchain_postgres import PGEngine, PGVectorStore
from sqlmodel import select

from db.session import async_engine
from models import Document, ChatSpaceDocument
from models.document import DocumentScope
from rag.context_manager import get_db_session
from rag.model import embeddings

pg_engine = PGEngine.from_engine(async_engine)


async def create_vector_store():
    vector_store = await PGVectorStore.create(
        engine=pg_engine,
        embedding_service=embeddings,
        table_name="document_chunks",
        id_column="chunk_id",
        metadata_columns=["document_id", "created_at"],
        metadata_json_column="meta",
    )
    return vector_store


@tool(response_format="content_and_artifact")
async def search_public_law(query: str):
    """
    This tool is designed for RAG in LLMs,
    specifically for searching Korean public laws.

    Args:
        query (str): The search query for public laws.

    """
    vector_store = await create_vector_store()
    relevant_chunks = []
    serialized = ""
    async with get_db_session() as session:
        statement = select(Document.document_id).where(
            Document.document_scope == DocumentScope.public_law
        )
        results = await session.execute(statement)
        target_doc_ids = results.scalars().all()
    if target_doc_ids:
        relevant_chunks = await vector_store.asimilarity_search(
            query, k=5, filter={"document_id": {"$in": target_doc_ids}}
        )
        serialized = "\n\n".join(
            f"Source: {doc.metadata}\nContent: {doc.page_content}"
            for doc in relevant_chunks
        )

    return serialized, relevant_chunks


@tool(response_format="content_and_artifact")
async def search_precedent(query: str):
    """
    This tool is designed for RAG in LLMs,
    specifically for searching Korean precedents.

    Args:
        query (str): The search query for precedents.

    """
    vector_store = await create_vector_store()
    relevant_chunks = []
    serialized = ""
    async with get_db_session() as session:
        statement = select(Document.document_id).where(
            Document.document_scope == DocumentScope.precedent
        )
        results = await session.execute(statement)
        target_doc_ids = results.scalars().all()
    if target_doc_ids:
        relevant_chunks = await vector_store.asimilarity_search(
            query, k=5, filter={"document_id": {"$in": target_doc_ids}}
        )
        serialized = "\n\n".join(
            f"Source: {doc.metadata}\nContent: {doc.page_content}"
            for doc in relevant_chunks
        )
    return serialized, relevant_chunks


@tool(response_format="content_and_artifact")
async def search_private_document(space_id: int, query: str):
    """
    This tool is designed for RAG in LLMs,
    specifically for searching private document chunks.

    Args:
        space_id (int): The ID of the chat space.
        query (str): The search query for precedents.

    """
    vector_store = await create_vector_store()
    relevant_chunks = []
    serialized = ""
    async with get_db_session() as session:
        statement = select(ChatSpaceDocument.space_document_id).where(
            ChatSpaceDocument.space_id == space_id
        )
        results = await session.execute(statement)
        target_doc_ids = results.scalars().all()
    if target_doc_ids:
        relevant_chunks = await vector_store.asimilarity_search(
            query, k=5, filter={"document_id": {"$in": target_doc_ids}}
        )
        serialized = "\n\n".join(
            f"Source: {doc.metadata}\nContent: {doc.page_content}"
            for doc in relevant_chunks
        )
    return serialized, relevant_chunks