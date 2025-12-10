import asyncio
import json
import logging

import unicodedata
from langchain.agents import create_agent
from rag.context_manager import get_db_session
from rag.model import llm
from rag.tools import (
    Context,
    search_precedent_by_case_number,
    search_precedent_semantic,
    search_private_documents,
    search_public_law_article,
    search_public_law_semantic,
    analyze_legal_problem,
)

from models import ChatSession
from models.chat_message import ChatMessage, ChatRole
from schemas.chat import ChatRequest

logger = logging.getLogger(__name__)


def agent_generator(include_law: bool = False, include_precedent: bool = False):
    tools = [search_private_documents]
    tools_string = ["search_private_documents"]
    deactivated_tools = []

    # [최적화 1] 역할 정의 및 기본 문서(Private) 우선순위 명시
    # 단순한 helpful assistant보다 'Legal Research Assistant'라는 페르소나를 부여하고,
    # 사용자가 업로드한 문서(Private)를 가장 먼저 고려하도록 지시합니다.
    prompt = """### Role
You are an expert Legal Research Assistant powered by RAG. Your goal is to provide accurate legal answers based on the provided tools.
You have access to:
1. **Private Documents**: User-uploaded files (contracts, briefs, etc.) -> **PRIORITY** if the user asks about "my file" or "this document".
2. **Public Laws**: Korean statutes and regulations.
3. **Precedents**: Korean court rulings and case laws.

### Core Instructions
- **Output Format**: When invoking a tool, output **ONLY the raw JSON**. Do not include any reasoning, thoughts, or "I will..." statements.
- **Precision**: Strictly follow the routing rules below."""

    if include_law:
        tools.append(search_public_law_semantic)
        tools.append(search_public_law_article)
        tools_string += ["search_public_law_semantic", "search_public_law_article"]
        # [최적화 2] 법령 검색 규칙을 'Condition-Action' 형태로 구조화
        prompt += """

### Law Search Guidelines
1. **Specific Article (Fast Track)**
   - **Condition**: User query contains 'Law Name'(법령명) + 'Article Number'(조) (e.g., "형법 제250조", "Civil Act Art 5").
   - **Action**: MUST use `search_public_law_article`.
   - **Constraint**: DO NOT use `search_public_law_semantic` for specific articles.

2. **Concept/Keyword Search**
   - **Condition**: User asks about definitions, legal concepts, or laws without specific numbers.
   - **Action**: Use `search_public_law_semantic`."""
    else:
        deactivated_tools += ["search_public_law_semantic", "search_public_law_article"]

    if include_precedent:
        tools.append(search_precedent_semantic)
        tools.append(search_precedent_by_case_number)
        tools_string += ["search_precedent_semantic", "search_precedent_by_case_number"]
        # [최적화 3] 판례 검색 규칙 구조화
        prompt += """

### Precedent Search Guidelines
1. **Specific Case Number (Fast Track)**
   - **Condition**: User query contains 'Case Number'(사건번호) (e.g., "2016헌마723", "2024도1234").
   - **Action**: MUST use `search_precedent_by_case_number`.
   - **Constraint**: DO NOT use `search_precedent_semantic` for exact case numbers.

2. **Semantic Search**
   - **Condition**: User looks for rulings on a topic, legal interpretation, or similar cases.
   - **Action**: Use `search_precedent_semantic`."""
    else:
        deactivated_tools += [
            "search_precedent_semantic",
            "search_precedent_by_case_number",
        ]

    if include_law and include_precedent:
        tools.append(analyze_legal_problem)
        # [최적화 4] 복합 전략을 단계별(Step-by-Step) 프로세스로 명시
        tools_string.append("analyze_legal_problem")
        prompt += """

### Advanced Strategy: Precedents by Law Article
**Scenario**: User asks for precedents related to a specific law article(조) (e.g., "민소법 300조 관련 판례").
**Execution Steps**:
1. **Retrieve Text**: Use `search_public_law_article` to get the full text of the article.
2. **Formulate Query**: Create a semantic query combining the **Article Number** AND **Key Legal Terms** found in the text.
3. **Search Precedents**: Use `search_precedent_semantic` with this enriched query.
   - *Reasoning*: Searching only by "Article 300" in vector DB is often insufficient. The text content improves accuracy.

### Complex Problem Solving Strategy
**Trigger**: User provides a Legal Exam Question (e.g., "문 5.", "다음 설명 중 옳은 것은?", Options A/B/C/D).

**Rule**:
1. **STOP GENERATING**: Do not try to solve the problem with your internal knowledge. You will likely hallucinate Article numbers.
2. **DELEGATE**: Call the tool `analyze_legal_problem` immediately.
3. **INPUT**: Pass the **full, unmodified question text** into the tool.
4. **SYNTHESIZE**: Once the tool returns the evidence report, use that evidence to determine which statements are Correct (O) or Incorrect (X), and then select the final answer (A, B, C, D, or E).

**TIPS**:
- If you can't find meaningful results from `search_public_law_semantic`, try `search_precedent_semantic`, instead of overusing `search_public_law_semantic`.
"""
    else:
        deactivated_tools.append("analyze_legal_problem")

    # [최적화 5] JSON 출력 강제 (마지막에 다시 한 번 강조)
    prompt += """
**WARNING**:
- NEVER invent Article numbers (e.g., Do not say '민법 1123조' if it doesn't exist).
- If you don't find the specific law/precedent via tools, admit you don't know rather than hallucinating.

### FINAL REMINDER
- No pre-text (e.g., "Let me check..."), No post-text.
- If no tool is needed, answer concisely.
- When using tools, return **ONLY JSON**.
- When generating the tool name, DO NOT append any special tokens like '<|channel|>', 'commentary', or thoughts."""

    agent = create_agent(
        model=llm,
        tools=tools,
        context_schema=Context,
        system_prompt=prompt,
    )
    return agent


async def save_chat_log(chats: list[ChatMessage]):
    try:
        async with get_db_session() as session:
            session.add_all(chats)
        logger.info("[CHAT] 채팅 로그 저장 성공")
    except Exception as e:
        logger.error(f"[CHAT] 채팅 로그 저장 실패: {e}")


# SSE 생성기 (Async Generator)
async def event_generator(session: ChatSession, request: ChatRequest):
    """
    1. 토큰을 클라이언트에게 실시간 전송 (SSE)
    2. 동시에 전체 답변을 full_response에 조립
    3. 완료 시 DB 저장
    """
    agent = agent_generator(request.include_law, request.include_precedent)
    normalized_query = unicodedata.normalize("NFC", request.query)
    new_question = ChatMessage(
        content=normalized_query, session_id=session.session_id, role=ChatRole.user
    )
    # 답변을 모을 버퍼
    full_response = ""
    sources = set()
    async for chunk, metadata in agent.astream(
        {"messages": [{"role": "user", "content": normalized_query}]},
        stream_mode="messages",
        context=Context(space_id=session.space_id),
    ):
        if metadata["langgraph_node"] == "model":
            full_response += chunk.content
        if metadata["langgraph_node"] == "tools":
            for doc in chunk.artifact:
                copied_doc = doc.copy()
                if "법령명" in copied_doc.metadata:
                    copied_doc.metadata["type"] = "public_law"
                elif "사건번호" in copied_doc.metadata:
                    copied_doc.metadata["type"] = "precedent"
                else:
                    copied_doc.metadata["type"] = "private"
                sources.add(copied_doc.metadata)
        yield f"data: {json.dumps({'token': chunk.content}, ensure_ascii=False)}\n\n"
    sources = list(sources)
    new_answer = ChatMessage(
        content=full_response,
        session_id=session.session_id,
        role=ChatRole.ai,
        sources=sources if sources else None,
    )
    asyncio.create_task(save_chat_log([new_question, new_answer]))
    # 스트림 종료 신호 (선택 사항)
    yield "data: [DONE]\n\n"
