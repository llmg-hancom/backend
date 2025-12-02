from langchain.tools import tool, ToolRuntime
from pydantic import BaseModel
from models.document import DocumentScope
from datetime import date

from rag.search import (
    fetch_target_ids,
    query_in_target,
    SearchFilter,
    query_in_precedent,
)


class Context(BaseModel):
    space_id: int


@tool(response_format="content_and_artifact", parse_docstring=True)
async def search_public_law_semantic(query: str):
    """
    This tool is designed for RAG in LLMs,
    specifically for semantic search for Korean public laws.

    Args:
        query (str): The search query for public laws.

    """
    relevant_chunks = []
    serialized = ""
    target_doc_ids = await fetch_target_ids(DocumentScope.public_law)
    if target_doc_ids:
        serialized, relevant_chunks = await query_in_target(query, target_doc_ids)
    return serialized, relevant_chunks


@tool(response_format="content_and_artifact", parse_docstring=True)
async def search_precedent_semantic(
    query: str, start_date: date | None = None, end_date: date | None = None
):
    """
    This tool is designed for RAG in LLMs,
    specifically for semantic search for Korean precedents.

    Args:
        query (str): The search query for precedents. This should be a concise and clear question or statement. DO NOT include case number(사건번호) or year/date here.
        start_date (date | None): Optional. The start date for filtering precedents by its decision date.
                                  Only precedents from this date onwards will be considered.
        end_date (date | None): Optional. The end date for filtering precedents by its decision date. Only precedents up to this date will be considered.

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
        query (str): The search query for precedents. This should be a concise and clear question or statement. DO NOT include case number(사건번호) or year/date here.
        case_numbers (list[str]): The case numbers (사건번호) to filter precedents by.

    """
    # 사건번호에 공백이 있는 경우 모두 제거
    case_numbers = [cn.replace(" ", "") for cn in case_numbers]
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
    target_doc_ids = await fetch_target_ids(
        DocumentScope.private, runtime.context.space_id
    )
    if target_doc_ids:
        serialized, relevant_chunks = await query_in_target(query, target_doc_ids)
    return serialized, relevant_chunks