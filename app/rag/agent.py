import asyncio
import json
import logging
import textwrap
from collections import defaultdict

import unicodedata
from langchain.agents import create_agent

from rag.context_manager import get_db_session
from rag.model import llm
from rag.tools import (
    Context,
    search_precedent_by_case_number,
    search_private_documents,
    search_public_law_article,
    search_public_law_semantic,
    analyze_legal_problem,
    search_precedent_semantic,
)

from models import ChatSession
from models.chat_message import ChatMessage, ChatRole
from schemas.chat import ChatRequest

logger = logging.getLogger(__name__)


def agent_generator(include_law: bool = False, include_precedent: bool = False):
    tools = [search_private_documents]

    # [최적화 1] 역할 정의 및 기본 문서(Private) 우선순위 명시
    # 단순한 helpful assistant보다 'Legal Research Assistant'라는 페르소나를 부여하고,
    # 사용자가 업로드한 문서(Private)를 가장 먼저 고려하도록 지시합니다.
    prompt = textwrap.dedent("""### Role
        You are an expert Legal Research Assistant powered by RAG. Your goal is to provide accurate legal answers based on the provided tools.
        You have access to:
        1. **Private Documents**: User-uploaded files (contracts, briefs, etc.) -> **PRIORITY** if the user asks about "my file" or "this document".
        2. **Precedents (Case Law)**: Korean court rulings. Vital for interpretation and application.
        3. **Public Laws (Statutes)**: Korean statutes and regulations. Basic definitions and rules.
        
        ### Core Instructions
        - **Output Format**: When invoking a tool, output **ONLY the raw JSON**. Do not include any reasoning.
        - **Precision**: Strictly follow the routing rules below.
        """)

    # 1. 특정 번호/기호가 있는 경우 (Fast Track) - 가장 먼저 처리
    prompt += ("\n### 1. Fast Track: Specific References (Highest Priority)\n"
               "If the user query contains specific identifiers, IGNORE semantic search and use these tools:\n")
    if include_law:
        tools.append(search_public_law_article)
        prompt += "- **Law Article** (e.g., '형법 제250조'): MUST use `search_public_law_article`.\n"

    if include_precedent:
        tools.append(search_precedent_by_case_number)
        prompt += "- **Case Number** (e.g., '2016헌마723'): MUST use `search_precedent_by_case_number`.\n"

    # 2. 의미 기반 검색 (Semantic Search Strategy) - 여기가 핵심 수정 부분
    if include_law or include_precedent:
        prompt += ("\n### 2. Semantic Search Strategy (Concept & Application)\n"
                   "When the user asks about legal concepts, situations, or interpretations without specific numbers:\n")

    # [핵심] 판례와 법령의 역할을 비교하여 우선순위 조정
    if include_law and include_precedent:
        tools.append(search_public_law_semantic)
        tools.append(search_precedent_semantic)
        prompt += textwrap.dedent("""
            **Decision Rule: Precedent vs. Law**
            1. **PRIORITIZE `search_precedent_semantic`** when:
               - The user asks **"How"** a law is applied in real life (e.g., "이 행위는 사기죄에 해당할까?").
               - The question involves specific **situations, scenarios, or disputes**.
               - The user asks for **judicial interpretation** or case examples.
            
            2. **Use `search_public_law_semantic`** ONLY when:
               - The user asks for the **static definition** of a term (e.g., "절도의 정의가 뭐야?").
               - The user asks if a specific regulation **exists**.
               - The user explicitly asks for "Law" or "Statute" text.
            
            🛑 SEMANTIC SEARCH TOOL USAGE GUIDELINES
            - **Legal Document Nature**: In most "consultation" style queries, \
            Precedents provide more valuable insights than raw Statutes. **Lean towards Precedents.**
            - **Semantic Search Nature**: The search tools use **Vector Embeddings**, not Keyword Matching.
            - **Do NOT Rephrase**: Asking the same question with slightly different words (e.g., changing "Contract Breach" to "Breach of Agreement") will yield the **EXACT SAME results**.
            - **Stop Condition**: If a search returns no relevant results, **do NOT try again** with a synonym. Assume the information does not exist in the database and move on.
            """)
        # 하나만 켜져 있는 경우의 예외 처리
    elif include_precedent:
        tools.append(search_precedent_semantic)
        prompt += "- Use `search_precedent_semantic` for all concept and situation queries.\n"

    elif include_law:
        tools.append(search_public_law_semantic)
        prompt += "- Use `search_public_law_semantic` for all concept and definition queries.\n"

    # 3. 복합 전략 및 문제 풀이 (기존 로직 유지하되 다듬음)
    if include_law and include_precedent:
        tools.append(analyze_legal_problem)
        prompt += textwrap.dedent("""

            ### 3. Advanced & Complex Strategies
            **Strategy A: Precedents by Law Article**
            - **Scenario**: User asks for precedents related to a specific law article (e.g., "민소법 300조 관련 판례").
            - **Action**: 
              1. Call `search_public_law_article` (get text).
              2. Call `search_precedent_semantic` (query = Statute name + Key Terms from text. (DO NOT include Article number(조) here.)).
            
            **Strategy B: Legal Exam / Multiple-Choice Questions**
            - **Trigger**: User provides a structured exam question (e.g., "문 5.", Options A/B/C/D).
            - **Action**: DO NOT solve it yourself. IMMEDIATELY call `analyze_legal_problem` with the **full unmodified text**.
            - **Warning**: NEVER use `analyze_legal_problem` more than once in a query. 
            - **Final Answer Structure**:
              1. **정답 (Correct Option)**: State the final answer clearly (e.g., "정답은 C입니다.").
              2. **상세 해설 (Detailed Explanation)**: Explain why each statement (ㄱ, ㄴ, ㄷ...) is correct or incorrect based on the evidence.
            """)

    # 기존의 무조건적인 "JSON ONLY" 제약을 조건부로 변경합니다.
    prompt += textwrap.dedent("""
        ### 🛑 CRITICAL FORMATTING RULES (READ CAREFULLY)
        
        **CASE 1: When you need more information (TOOL CALLING PHASE)**
        - If you need to search private documents, laws, precedents, or analyze the problem, you MUST invoke a tool.
        - **Format**: Output **ONLY the raw JSON** for the tool call.
        - **Prohibited**: Do NOT output any text, reasoning, or explanations outside the JSON.
        
        **CASE 2: When you have sufficient information (FINAL ANSWER PHASE)**
        - If you have received the tool outputs and are ready to answer the user.
        - **Format**: Output **Natural Language (Korean)**. Use Markdown for readability.
        - **Prohibited**: Do NOT output JSON here. Do NOT say "I have analyzed...". Just give the answer.
        
        ### FINAL REMINDER
        - DO NOT output "analysis" anywhere.
        - DO NOT invent Article numbers.
        - DO NOT answer legal questions without using any tool.
        - Do NOT rephrase using the same semantic search tool.
        - 질문이 한국어면 **항상** 한국어를 사용하세요.
        """)
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
    full_response: list[str] = []
    # 중복 출처 표시를 막기 위한 장치
    sources: list[dict] = []
    sources_id: set[int] = set()
    statute_articles: defaultdict[str, set] = defaultdict(set)
    async for chunk, metadata in agent.astream(
            {"messages": [{"role": "user", "content": normalized_query}]},
            stream_mode="messages",
            context=Context(space_id=session.space_id),
    ):
        if metadata["langgraph_node"] == "model":
            full_response.append(chunk.content)
        if metadata["langgraph_node"] == "tools" and chunk.artifact:
            for doc in chunk.artifact:
                if doc.metadata.get("document_id") in sources_id:
                    statute: str | None = doc.metadata.get("법령명")
                    if statute is None:
                        continue
                    else:
                        if doc.metadata.get("조") in statute_articles.get(statute, []):
                            continue
                copied_doc = doc.copy()
                sources_id.add(copied_doc.metadata.get("document_id"))
                if "법령명" in copied_doc.metadata:
                    statute_articles[copied_doc.metadata.get("법령명")].add(copied_doc.metadata.get("조", "없음"))
                    copied_doc.metadata["type"] = "public_law"
                elif "사건번호" in copied_doc.metadata:
                    copied_doc.metadata["type"] = "precedent"
                else:
                    copied_doc.metadata["type"] = "private"
                sources.append(copied_doc.metadata)
        yield f"data: {json.dumps({'token': chunk.content}, ensure_ascii=False)}\n\n"
    new_answer = ChatMessage(
        content="".join(full_response),
        session_id=session.session_id,
        role=ChatRole.ai,
        sources=sources if sources else None,
    )
    asyncio.create_task(save_chat_log([new_question, new_answer]))
    # 스트림 종료 신호 (선택 사항)
    yield "data: [DONE]\n\n"
