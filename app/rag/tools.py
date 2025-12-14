import json
import textwrap
from datetime import date

from langchain.agents import AgentState
from langchain.tools import ToolRuntime, tool
from langchain_core.documents import Document as LCDocument
from langchain_core.messages import ToolMessage, SystemMessage
from langgraph.types import Command
from pydantic import BaseModel, Field

from models.statute import StatuteType
from rag.search import (
    fetch_target_ids,
    find_law_by_article,
    query_in_target,
    legal_similarity_search,
    StatuteFilter,
    PrecedentFilter, query_private_document,
)
from rag.law_category import StatuteTitle, LAW_ALIAS_MAP, search_statute_title

from rag.cleaning import split_problem_into_statements_regex

PRECEDENT_HEADERS = [
    "법원명", "사건번호", "사건명", "선고일자", "선고",
    "참조조문", "참조판례", "판결유형", "사건종류명",
]

COURT_PRECEDENT_HEADERS = [
    "사건번호", "사건명", "종국일자",
    "심판대상조문", "참조조문", "참조판례", "판결유형", "사건종류명",
]
COMMON_MISNOMERS = {"법인법", "회사법", "주식회사법", "기업법", "상사법",
                    "계약법", "불법행위법", "채권법", "친족상속법", "가정법원법"}


class CustomState(AgentState):
    searched_chunks: list[int]


class Context(BaseModel):
    space_id: int


def format_doc(doc: LCDocument) -> str:
    """llm에게 줄 정보 제한 및 추출"""

    if "선고일자" in doc.metadata:  # 일반 판례인 경우
        meta_parts = [
            f"'{k}': {v}"
            for k in PRECEDENT_HEADERS
            # 값이 존재하고(None 아님) 빈 문자열이나 "정보없음"도 아닌 경우
            if (v := doc.metadata.get(k)) and v != "정보없음"
        ]
        summary = doc.metadata.get("판결요지")
        points = doc.metadata.get("판시사항")
    elif "종국일자" in doc.metadata:  # 헌재 판례인 경우
        meta_parts = ["'법원명': 헌법재판소"] + [
            f"'{k}': {v}"
            for k in COURT_PRECEDENT_HEADERS
            # 값이 존재하고(None 아님) 빈 문자열이나 "정보없음"도 아닌 경우
            if (v := doc.metadata.get(k)) and v != "정보없음"
        ]
        summary = doc.metadata.get("판결요지")
        points = doc.metadata.get("판시사항")
    else:  # 나머지 문서의 경우 (법령, 개인 문서)
        meta_parts = [
            f"'{k}': {v}"
            for k, v in doc.metadata.items()
            # key가 document_id가 아니고, 값이 존재하고(None 아님) 빈 문자열이나 "정보없음"도 아닌 경우
            if k != "document_id" and v and v != "정보없음"
        ]

        # 3. 메타데이터와 본문 결합
        meta_str = ", ".join(meta_parts)
        return f"Source: {meta_str}\nContent: {doc.page_content}"

    content: str = ""
    if summary:
        content += f"'판시사항': {summary}\n"
    if points:
        content += f"'판결요지': {points}\n"

    if not content:
        content = doc.page_content
    else:
        if len(content) <= 300:
            content = content + doc.page_content

    # 3. 메타데이터와 본문 결합
    meta_str = ", ".join(meta_parts)
    return f"Source: {meta_str}\nSummary: {content}"


async def find_statute_title(query: str) -> tuple[StatuteTitle | str | list[str], bool]:
    clean_input = query.replace(" ", "").replace("(법률)", "")

    if clean_input in LAW_ALIAS_MAP:
        return LAW_ALIAS_MAP[clean_input], True

    # Enum 멤버들과 비교
    for member in StatuteTitle:
        # DB 값 정규화: 공백 제거
        # 예: "개인정보 보호법" -> "개인정보보호법"
        normalized_member = member.value.replace(" ", "")

        # 정규화된 값이 일치하면, DB에 저장된 '정확한 값(member)'을 반환
        if clean_input == normalized_member:
            return member, True
    # 주요 법이 아니라 Enum 안에 없는 경우 DB를 통해 법령명 Hybrid Search 실행
    candidates = await search_statute_title(query)
    # Hybrid Search로 검색된 결과의 법령명과 약칭 중에 정확한 일치가 있는 경우
    for candidate in candidates:
        if (
                candidate.title.replace(" ", "") == clean_input
                or clean_input in candidate.alias
        ):
            return candidate.title, True
    return [item.title for item in candidates], False


class SearchLawSemanticInput(BaseModel):
    query: str = Field(
        description="The search query for public laws. This should be a concise and clear question or statement.\n"
                    "DO NOT include statute article number(조) here.")
    statute_name: str | None = Field(
        default=None,
        description="Optional. The name or abbreviation of the statute(법령명) to search for."
    )


@tool(args_schema=SearchLawSemanticInput)
async def search_public_law_semantic(runtime: ToolRuntime[Context, CustomState],
                                     query: str, statute_name: str | None = None, ):
    """
    Searches for public laws based on semantic meaning.
    Use this tool for searching legal concepts, definitions related to specific laws.
    You can specify 'Statute Name'(법령명) to search from.

    ⚠️ CRITICAL INSTRUCTION:
    1. If the user provides a specific 'Statute Name'(법령명) AND 'Article Number'(조), DO NOT use this tool. Use 'search_public_law_article' instead.
    2. If the user wants to read the raw TEXT of a law article (e.g., "민사소송법 5조를 읽어줘"), DO NOT use this tool. Use 'search_public_law_article'.
    3. Do NOT invent statute names.
    4. **Do NOT Rephrase**: Asking the same question with slightly different words or order will yield the **EXACT SAME results**.
    """
    header = ""
    # 법령명이 주어졌을때, 법령명이 약칭을 포함해 정확하면 그 법령명에서만 검색, 정확하지 않으면 관련성 높은 5개 법령명에서 검색
    if statute_name:
        exact_name, is_exact = await find_statute_title(statute_name)
        if is_exact:
            statute_filter = StatuteFilter(titles=[exact_name])
        else:
            statute_filter = StatuteFilter(titles=exact_name)
            header = (
                f"[System Message]\n'{statute_name}' is NOT a valid Korean statute title. DO NOT invent statute names.\n"
                f"Results are from the following statutes instead: {', '.join(exact_name)}\n")
    # 법령명이 주어지지 않으면 전체 범위에서 검색
    else:
        statute_filter = None

    relevant_chunks = await legal_similarity_search(
        query,
        "public_law",
        statute_filter=statute_filter,
        k=8,
        fetch_k=60,
        ef_search=120,
    )
    if not relevant_chunks:
        return (
                header +
                textwrap.dedent(f"""
                [System Message]
                No relevant law articles found. 
                NOTE: Since this is a semantic search, rephrasing the query with synonyms will likely fail again.
                Please STOP searching for this specific topic and try a completely different legal concept, \
                try 'search_precedent_semantic' instead, or conclude that no information is available.
                """)
        ), []
    already_searched: set[int] = set(runtime.state.get("searched_chunks", []))
    new_searches = {ci for doc in relevant_chunks if (ci := doc.metadata.get("chunk_id")) not in already_searched}
    updated_set = already_searched.union(new_searches)
    serialized = (f"{header}{"\n\n".join(format_doc(doc) for doc in relevant_chunks)}\n"
                  f"[System Message]\n**WARNING**: DO NOT call 'search_public_law_semantic' with similar query even if the results are irrelevant.")
    return Command(
        update={"searched_chunks": list(updated_set),
                "messages": [
                    ToolMessage(content=serialized, artifact=relevant_chunks, tool_call_id=runtime.tool_call_id),
                ]})


class SearchLawArticleInput(BaseModel):
    statute_title: str = Field(
        description="The name or abbreviation of the statute(법령명) to search for."
    )
    article: int = Field(
        description=(
            "The article number(조) of the law to search for."
            "You need to input number that comes before `조`, NOT after. (e.g. `제5조의10` -> `5`)"
        )
    )


@tool(args_schema=SearchLawArticleInput)
async def search_public_law_article(runtime: ToolRuntime[Context, CustomState], statute_title: str, article: int):
    """
    Retrieves the exact TEXT of a specific law article.
    Use this tool ONLY when you have the specific 'Statute Name'(법령명) AND 'Article Number'(조).

    Examples:
    - User: "민법 5조가 뭐야?" -> Use this tool.
    - User: "형법 250조의 내용을 알려줘." -> Use this tool.

    ⚠️ CRITICAL INSTRUCTION:
    1. Do NOT use this tool for searching precedents or general legal concepts.
    2. Do NOT use this tool if you have only 'Statute Name'(법령명) without 'Article Number'(조). Use "search_public_law_semantic" instead.
    """
    header = ""
    exact_title, is_exact = await find_statute_title(statute_title)
    if not is_exact:
        exact_title = exact_title[0]
        header = (
            f"[System Message]\n'{statute_title}' is NOT a valid Korean statute title. DO NOT invent statute names.\n"
            f"Results are from the following statute instead: {exact_title}\n")
    else:
        if statute_title in COMMON_MISNOMERS:
            header = (
                f"[System Message]\n'{statute_title}' is NOT a valid Korean statute title.\n"
                f"Use the following statute title instead: {exact_title}\n")
    relevant_chunks = await find_law_by_article(exact_title, article)
    if not relevant_chunks:
        return (
            header +
            textwrap.dedent("""
                [System Message]
                법령 조문 검색 실패.
                """),
            [],
        )
    already_searched: set[int] = set(runtime.state.get("searched_chunks", []))
    new_searches = {ci for doc in relevant_chunks if (ci := doc.metadata.get("chunk_id")) not in already_searched}
    updated_set = already_searched.union(new_searches)
    serialized = (
            header
            + f"'법령명': {exact_title}\n"
            + "\n".join(doc.page_content for doc in relevant_chunks)
    )
    return Command(
        update={"searched_chunks": list(updated_set),
                "messages": [
                    ToolMessage(content=serialized, artifact=relevant_chunks, tool_call_id=runtime.tool_call_id),
                ]}
    )


# 입력 스키마 정의
class SearchPrecedentSemanticInput(BaseModel):
    query: str = Field(
        description=(
            "The search query for precedents. This should be a concise and clear question or statement.\n"
            "DO NOT include statute article number(조), case number(사건번호) or year/date here."
        )
    )
    start_date: date | None = Field(
        default=None,
        description="Optional. The start date for filtering precedents by its decision date. Only precedents from this date onwards will be considered.",
    )
    end_date: date | None = Field(
        default=None,
        description="Optional. The end date for filtering precedents by its decision date. Only precedents up to this date will be considered.",
    )


@tool(args_schema=SearchPrecedentSemanticInput)
async def search_precedent_semantic(runtime: ToolRuntime[Context, CustomState],
                                    query: str, start_date: date | None = None, end_date: date | None = None):
    """
    Searches for legal precedents (court rulings) based on semantic meaning.
    Use this tool for searching legal concepts, definitions, or precedents related to specific laws.
    ⚠️ CRITICAL INSTRUCTION:
    1. If the user provides a specific 'Case Number' (e.g., '2025도903'), DO NOT use this tool. Use 'search_precedent_by_case_number' instead.
    2. If the user wants to read the raw TEXT of a law article (e.g., "민사소송법 5조를 읽어줘"), DO NOT use this tool. Use 'search_public_law_article'.
    3. HOWEVER, if the user asks for "민사소송법 5조 관련 판례", use this tool after searching for law article.
    4. **Do NOT Rephrase**: Asking the same question with slightly different words or order will yield the **EXACT SAME results**.

    """
    precedent_filter = PrecedentFilter(start_date=start_date, end_date=end_date)
    relevant_chunks = await legal_similarity_search(
        query, "precedent", precedent_filter=precedent_filter, fetch_k=40, ef_search=100
    )
    if not relevant_chunks:
        return (
            textwrap.dedent("""
                [System Message]
                No relevant precedents found. 
                NOTE: Since this is a semantic search, rephrasing the query with synonyms will likely fail again.
                Please STOP searching for this specific topic and try a completely different legal concept,\
                try 'search_public_law_semantic' instead, or conclude that no information is available.or conclude that no information is available.
                """),
            [],
        )
    already_searched: set[int] = set(runtime.state.get("searched_chunks", []))
    new_searches = {ci for doc in relevant_chunks if (ci := doc.metadata.get("chunk_id")) not in already_searched}
    updated_set = already_searched.union(new_searches)
    serialized = ("\n\n".join(format_doc(doc) for doc in relevant_chunks) +
                  f"\n[System Message]\n"
                  f"**WARNING**: DO NOT call 'search_precedent_semantic' with similar query even if the results are irrelevant.")
    return Command(
        update={"searched_chunks": list(updated_set),
                "messages": [
                    ToolMessage(content=serialized, artifact=relevant_chunks, tool_call_id=runtime.tool_call_id),
                ]}
    )


class SearchPrecedentCaseNumber(BaseModel):
    query: str = Field(
        description="The semantic query to run INSIDE the specified case document (e.g., 'What was the sentence?', '판결요지')."
    )
    case_number: str = Field(
        description="The exact case number to filter by. (e.g., '2025도903', '2024가합123')"
    )


@tool(args_schema=SearchPrecedentCaseNumber)
async def search_precedent_by_case_number(runtime: ToolRuntime[Context, CustomState], query: str, case_number: str):
    """
    Searches for precedents within specific 'Case Number'(사건번호).
    Use this tool ONLY when you have exact case number (e.g., '2025도903').

    ⚠️ CRITICAL INSTRUCTION:
    The 'query' parameter must NOT contain the case number itself. It should be the topic to search *inside* that case.
    If there is no specific topic, use a general summary query like "판결요지".
    """
    # 사건번호에 공백이 있는 경우 제거
    case_number = case_number.replace(" ", "")
    precedent_filter = PrecedentFilter(case_number=case_number)
    relevant_chunks = await legal_similarity_search(
        query, "precedent", precedent_filter=precedent_filter, k=3
    )
    if not relevant_chunks:
        return (
            textwrap.dedent("""
                [System Message]
                사건번호 검색 실패.
                """),
            [],
        )
    already_searched: set[int] = set(runtime.state.get("searched_chunks", []))
    new_searches = {ci for doc in relevant_chunks if (ci := doc.metadata.get("chunk_id")) not in already_searched}
    updated_set = already_searched.union(new_searches)
    header = format_doc(relevant_chunks[0])
    serialized = f"{header}\nContents:\n" + "\n\n".join(
        f"{f"섹션명: {section}\n" if (section := doc.metadata.get('섹션명')) else f"검색 결과{i + 1} "}내용: {doc.page_content}"
        for i, doc in enumerate(relevant_chunks))
    return Command(
        update={"searched_chunks": list(updated_set),
                "messages": [
                    ToolMessage(content=serialized, artifact=relevant_chunks, tool_call_id=runtime.tool_call_id),
                ]}
    )


# noinspection PyIncorrectDocstring
@tool(parse_docstring=True)
async def search_private_documents(query: str, runtime: ToolRuntime[Context, CustomState]):
    """
    Searches for information within the USER UPLOADED private documents based on semantic meaning.
    Use this tool when the user asks about their own files, contracts, or specific documents they provided.

    ⚠️ CRITICAL INSTRUCTION:
    1. If the user query contains a specific case number (e.g., '2001나60578'), DO NOT use this tool. Use 'search_precedent_by_case_number'.
    2. Do not use this for general legal knowledge or public laws unless the user specifically asks about their file's content regarding it.
    3. **Do NOT Rephrase**: Asking the same question with slightly different words or order will yield the **EXACT SAME results**.

    Args:
        query (str): The search query for private documents.
    """
    target_doc_ids = await fetch_target_ids(runtime.context.space_id)
    if target_doc_ids:
        relevant_chunks = await query_private_document(query, runtime.context.space_id)
    else:
        return (
            textwrap.dedent("""
                [System Message]
                There is no document attached to the chat session. DO NOT call this tool again.
                """),
            [],
        )
    already_searched: set[int] = set(runtime.state.get("searched_chunks", []))
    new_searches = {ci for doc in relevant_chunks if (ci := doc.metadata.get("chunk_id")) not in already_searched}
    updated_set = already_searched.union(new_searches)
    serialized = "\n\n".join(format_doc(doc) for doc in relevant_chunks)
    return Command(
        update={"searched_chunks": list(updated_set),
                "messages": [
                    ToolMessage(content=serialized, artifact=relevant_chunks, tool_call_id=runtime.tool_call_id),
                ]}
    )


@tool(response_format="content_and_artifact", parse_docstring=True)
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

    ⚠️ CRITICAL INSTRUCTION:
    - DO NOT call this tool more than once.

    Args:
        problem_text (str): The raw text of the problem.
    """
    # 1. LLM을 이용해 문제를 A, B, C, D 지문으로 분리 (파이썬 로직 또는 가벼운 LLM 호출)
    background, statements = split_problem_into_statements_regex(problem_text)
    if background == "":
        return "[System Message]유효한 객관식 문제가 아닙니다. 다른 도구를 이용하세요.", []

    target_statutes = await search_statute_title(
        background, statute_type=StatuteType.ACT
    )
    target_statute_titles = [s.title for s in target_statutes]

    results = [
        f"[사실관계] {background}\n[관련 법령명] {', '.join(target_statute_titles)}"
    ]
    relevant_chunks: list[LCDocument] = []
    for stmt in statements:
        chunks = await legal_similarity_search(
            background + "\n" + stmt,
            statute_filter=StatuteFilter(titles=target_statute_titles),
            k=3,
        )
        search_res = "\n\n".join(
            format_doc(doc) for doc in chunks
        )
        results.append(f"[지문] {stmt}\n관련 법령/판례: [{search_res}]")
        relevant_chunks += chunks

    return "\n\n".join(results), relevant_chunks
