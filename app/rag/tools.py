from datetime import date

from langchain.tools import ToolRuntime, tool
from pydantic import BaseModel, Field, field_validator
from rag.search import (
    SearchFilter,
    fetch_target_ids,
    find_law_by_article,
    query_in_precedent,
    query_in_target,
    fetch_private_ids,
    query_excluding_target,
)
from rag.law_category import LawName, LAW_ALIAS_MAP

from models.document import DocumentScope
from rag.cleaning import split_problem_into_statements_regex


class Context(BaseModel):
    space_id: int


@tool(response_format="content_and_artifact", parse_docstring=True)
async def search_public_law_semantic(query: str):
    """
    Searches for public laws based on semantic meaning.
    Use this tool for searching legal concepts, definitions related to specific laws.
    ⚠️ CRITICAL INSTRUCTION:
    1. If the user provides a specific 'Law Name'(법령명) and 'Article Number'(조), DO NOT use this tool. Use 'search_public_law_article' instead.
    2. If the user wants to read the raw TEXT of a law article (e.g., "민사소송법 5조를 읽어줘"), DO NOT use this tool. Use 'search_public_law_article'.

    Args:
        query (str): The search query for public laws.

    """
    relevant_chunks = []
    serialized = ""
    target_doc_ids = await fetch_target_ids(DocumentScope.public_law)
    if target_doc_ids:
        serialized, relevant_chunks = await query_in_target(query, target_doc_ids)
    return serialized, relevant_chunks


class SearchLawInput(BaseModel):
    law_name: str = Field(description="The name of the law(법령명) to search for.")
    article: int = Field(description="The article number(조) of the law to search for.")

    @field_validator("law_name")
    @classmethod
    def normalize_law_name(cls, v: str) -> str:
        # 입력값 정규화: 공백 제거 및 '(법률)' 제거
        # 예: "개인정보 보호법" -> "개인정보보호법"
        clean_input = v.replace(" ", "").replace("(법률)", "")

        if clean_input in LAW_ALIAS_MAP:
            return LAW_ALIAS_MAP[clean_input]

        # Enum 멤버들과 비교
        for member in LawName:
            # DB 값 정규화: 공백 제거
            # 예: "개인정보 보호법" -> "개인정보보호법"
            normalized_member = member.value.replace(" ", "")

            # 정규화된 값이 일치하면, DB에 저장된 '정확한 값(member)'을 반환
            if clean_input == normalized_member:
                return member

        raise ValueError(
            f"지원하지 않거나 정확하지 않은 법률 명칭입니다: {v}. (가능한 목록: 형법, 행정소송법, 근로기준법...)"
        )


@tool(
    response_format="content_and_artifact",
    args_schema=SearchLawInput,
)
async def search_public_law_article(law_name: LawName, article: int):
    """
    Retrieves the exact TEXT of a specific law article.
    Use this tool ONLY when you have the specific 'Law Name'(법령명) AND 'Article Number'(조).

    Examples:
    - User: "민법 5조가 뭐야?" -> Use this tool.
    - User: "형법 250조의 내용을 알려줘." -> Use this tool.

    Do NOT use this tool for searching precedents or general legal concepts.
    """
    serialized, relevant_chunks = await find_law_by_article(law_name, article)
    return serialized, relevant_chunks


@tool(response_format="content_and_artifact", parse_docstring=True)
async def search_precedent_semantic(
    query: str, start_date: date | None = None, end_date: date | None = None
):
    """
    Searches for legal precedents (court rulings) based on semantic meaning.
    Use this tool for searching legal concepts, definitions, or precedents related to specific laws.
    ⚠️ CRITICAL INSTRUCTION:
    1. If the user provides a specific 'Case Number' (e.g., '2025도903'), DO NOT use this tool. Use 'search_precedent_by_case_number' instead.
    2. If the user wants to read the raw TEXT of a law article (e.g., "민사소송법 5조를 읽어줘"), DO NOT use this tool. Use 'search_public_law_article'.
    3. HOWEVER, if the user asks for "민사소송법 5조 관련 판례", use this tool after searching for law article.

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
    Searches for precedents within specific 'Case Numbers'(사건번호).
    Use this tool ONLY when the user provides exact case numbers (e.g., '2025도903').

    ⚠️ CRITICAL INSTRUCTION:
    The 'query' parameter must NOT contain the case number itself. It should be the topic to search *inside* that case.
    If there is no specific topic, use a general summary query like "Summary of the case".

    Args:
        query (str): The semantic query to run INSIDE the specified case document (e.g., "What was the sentence?", "Summary").
        case_numbers (list[str]): List of exact case numbers to filter by. (e.g., ["2025도903", "2024가합123"])

    """
    # 사건번호에 공백이 있는 경우 모두 제거
    case_numbers = [cn.replace(" ", "") for cn in case_numbers]
    search_filter = SearchFilter(case_numbers=case_numbers)
    serialized, relevant_chunks = await query_in_precedent(query, search_filter)
    return serialized, relevant_chunks


# noinspection PyIncorrectDocstring
@tool(response_format="content_and_artifact", parse_docstring=True)
async def search_private_documents(query: str, runtime: ToolRuntime[Context]):
    """
    Searches for information within the USER UPLOADED private documents.
    Use this tool when the user asks about their own files, contracts, or specific documents they provided.

    ⚠️ CRITICAL INSTRUCTION:
    1. If the user query contains a specific case number (e.g., '2001나60578'), DO NOT use this tool. Use 'search_precedent_by_case_number'.
    2. Do not use this for general legal knowledge or public laws unless the user specifically asks about their file's content regarding it.

    Args:
        query (str): The search query for private documents.
    """
    relevant_chunks = []
    target_doc_ids = await fetch_target_ids(
        DocumentScope.private, runtime.context.space_id
    )
    if target_doc_ids:
        serialized, relevant_chunks = await query_in_target(query, target_doc_ids)
    else:
        serialized = "Empty: There is no document attached to the chat session. DO NOT call this tool again."
    return serialized, relevant_chunks


@tool(parse_docstring=True)
async def analyze_legal_problem(problem_text: str):
    """
    **PRIMARY TOOL for Legal Exam/Multiple-Choice Questions.**

    Use this tool IMMEDIATELY when the user asks to solve a problem that includes:
    1. A background story or factual scenario (Case).
    2. Multiple statements/options to verify (e.g., labeled as ㄱ, ㄴ, ㄷ, ㄹ or ①, ②, ③).
    3. Phrases like "다툼이 있는 경우 판례에 의함" (According to precedents if disputed).

    **Functionality**:
    - It automatically decomposes the complex problem into individual legal claims.
    - It searches for Evidence (Laws & Precedents) for EACH statement separately.
    - It returns a consolidated fact-check report.

    **Input**:
    - The ENTIRE raw text of the problem. Do not summarize or split it yourself.

    **Why use this?**:
    - Standard search tools cannot handle complex multi-part questions effectively.
    - Using this tool prevents hallucinations about Article numbers(조).

    Args:
        problem_text (str): The raw text of the problem.
    """
    # 1. LLM을 이용해 문제를 A, B, C, D 지문으로 분리 (파이썬 로직 또는 가벼운 LLM 호출)
    statements = split_problem_into_statements_regex(problem_text)

    results = []
    for stmt in statements:
        excluded_doc_ids = await fetch_private_ids()
        search_res, relevant_chunks = await query_excluding_target(
            stmt,
            excluded_doc_ids,
            excluded_meta_keys=[
                "사건요지",
                "판례상세링크",
                "법원종류코드",
                "사건종류코드",
                "판례정보일련번호",
                "document_id",
            ],
            k=3,
        )
        results.append(f"지문: {stmt}\n관련 법령/판례: [{search_res}]")

    return "\n\n".join(results)