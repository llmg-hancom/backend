from datetime import date

from langchain.tools import ToolRuntime, tool
from pydantic import BaseModel, Field, field_validator
from rag.search import (
    LawCategory,
    SearchFilter,
    fetch_target_ids,
    find_law_by_article,
    query_in_precedent,
    query_in_target,
)

from models.document import DocumentScope


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


# 법률 이름 약어 매핑
LAW_ALIAS_MAP = {
    # 1. 민사소송법 (Civil Procedure)
    "민소법": LawCategory.CIVIL_PROCEDURE,
    "민소": LawCategory.CIVIL_PROCEDURE,
    # 2. 형사소송법 (Criminal Procedure)
    "형소법": LawCategory.CRIMINAL_PROCEDURE,
    "형소": LawCategory.CRIMINAL_PROCEDURE,
    # 3. 근로기준법 (Labor Standards) -> 실무에서 가장 많이 줄여 씀
    "근기법": LawCategory.LABOR,
    "근로법": LawCategory.LABOR,
    "노동법": LawCategory.LABOR,  # 엄밀히는 노동조합법 등도 포함하지만, 일반인은 근기법을 의도하는 경우가 많음
    # 4. 최저임금법 (Minimum Wage)
    "최임법": LawCategory.MINIMAL_WAGE,
    # 5. 개인정보 보호법 (Personal Info) -> 매우 흔함
    "개보법": LawCategory.PERSONAL_INFORMATION,
    "개인정보법": LawCategory.PERSONAL_INFORMATION,
    # 6. 산업안전보건법 (Occupational Safety) -> 현장에서 매우 흔함
    "산안법": LawCategory.OCCUPATIONAL_SAFETY,
    "산업안전법": LawCategory.OCCUPATIONAL_SAFETY,
    # 7. 행정기본법 (Framework Act on Admin)
    "행기법": LawCategory.FRAMEWORK_ACT,
    # 8. 행정소송법 (Admin Litigation)
    "행소법": LawCategory.FRAMEWORK_PROCEDURE,  # '형소법'과 발음 주의, 텍스트로는 명확함
    "행정소송": LawCategory.FRAMEWORK_PROCEDURE,
    # 9. 행정심판법 (Admin Appeals)
    "행심법": LawCategory.ADMINISTRATIVE_APPEALS,
    "행정심판": LawCategory.ADMINISTRATIVE_APPEALS,
    # 10. 헌법재판소법 (Constitutional Court)
    "헌재법": LawCategory.CONSTITUTIONAL_COURT,
    # 11. 국민연금법 (Pension)
    "연금법": LawCategory.PENSION,
    # 12. 국민건강보험법 (Health Insurance)
    "건보법": LawCategory.HEALTH_INSURANCE,
    "건강보험법": LawCategory.HEALTH_INSURANCE,
    # 13. 가족관계의 등록 등에 관한 법률 (Family) -> 이름이 길어서 필수
    "가족관계등록법": LawCategory.FAMILY,
    "가족관계법": LawCategory.FAMILY,
    "가족법": LawCategory.FAMILY,  # 민법 친족/상속편을 의미할 수도 있으나, 맥락상 허용
    "가등록법": LawCategory.FAMILY,
}


class SearchLawInput(BaseModel):
    category: str = Field(description="The category of the law(법령명) to search for.")
    article: int = Field(description="The article number(조) of the law to search for.")

    @field_validator("category")
    @classmethod
    def normalize_law_name(cls, v: str) -> str:
        # 입력값 정규화: 공백 제거 및 '(법률)' 제거
        # 예: "개인정보 보호법" -> "개인정보보호법"
        clean_input = v.replace(" ", "").replace("(법률)", "")

        if clean_input in LAW_ALIAS_MAP:
            return LAW_ALIAS_MAP[clean_input]

        # Enum 멤버들과 비교
        for member in LawCategory:
            # DB 값 정규화: 공백 제거 및 '(법률)' 제거
            # 예: "개인정보 보호법(법률)" -> "개인정보보호법"
            normalized_member = member.value.replace(" ", "").replace("(법률)", "")

            # 정규화된 값이 일치하면, DB에 저장된 '정확한 값(member.value)'을 반환
            if clean_input == normalized_member:
                return member

        raise ValueError(
            f"지원하지 않거나 정확하지 않은 법률 명칭입니다: {v}. (가능한 목록: 형법, 행정소송법, 근로기준법...)"
        )


@tool(
    response_format="content_and_artifact",
    args_schema=SearchLawInput,
)
async def search_public_law_article(category: LawCategory, article: int):
    """
    This tool is designed for RAG in LLMs,
    specifically for searching for Korean public laws by its category and article.
    """
    serialized, relevant_chunks = await find_law_by_article(category, article)
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


# noinspection PyIncorrectDocstring
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