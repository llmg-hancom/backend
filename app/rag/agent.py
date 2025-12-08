import asyncio
import json
import logging

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
)

from models import ChatSession
from models.chat_message import ChatMessage, ChatRole
from schemas.chat import ChatRequest


logger = logging.getLogger(__name__)


def agent_generator(include_law: bool = False, include_precedent: bool = False):
    tools = [search_private_documents]
    prompt = """You are a helpful assistant specialized in Korean law,
        and answers questions about private documents users uploaded using RAG."""
    if include_law:
        tools.append(search_public_law_semantic)
        tools.append(search_public_law_article)
        prompt += (
            "\n[Law Search Rules]"
            "\n1. First, analyze if the user provided a specific 'Law Name'(법령명) and 'Article Number'(조) (e.g., 형법 제250조)."
            "\n2. IF specific article is present: YOU MUST use 'search_public_law_article'."
            "\n   - DO NOT use 'search_public_law_semantic' in this case."
            "\n3. IF NO specific article is present (concept search): Use 'search_public_law_semantic'."
        )
    if include_precedent:
        tools.append(search_precedent_semantic)
        tools.append(search_precedent_by_case_number)
        prompt += (
            "\n[Precedent Search Rules]"
            "\n1. First, analyze if the user provided a specific 'Case Number'(사건번호) (e.g., 2016헌마723)."
            "\n2. IF specific case number is present: YOU MUST use 'search_precedent_by_case_number'."
            "\n   - DO NOT use 'search_precedent_semantic' in this case."
            "\n3. IF NO specific Case Number is present (concept search): Use 'search_precedent_semantic'."
        )
    if include_law and include_precedent:
        prompt += (
            "\n[Search Strategy for Precedents based on Law Articles]"
            "\n1. IF the user asks for precedents related to a specific law article(조) (e.g., '민소법 300조 관련 판례'),"
            "\n   DO NOT search for precedents immediately."
            "\n2. STEP 1: First, use 'search_public_law_article' to retrieve the full TEXT and meaning of that article."
            "\n3. STEP 2: Then, formulate a rich semantic query using both the article number AND its content/keywords obtained from STEP 1."
            "\n4. STEP 3: Use 'search_precedent_semantic' with this enriched query."
        )
    prompt += (
        "\nBe concise and accurate."
        "\n[IMPORTANT]"
        "\nWhen you need to use a tool, output ONLY the raw JSON for the tool call."
        "Do not output any reasoning, thoughts, or explanations before or after the JSON."
        "Just the JSON."
    )
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
    new_question = ChatMessage(
        content=request.query, session_id=session.session_id, role=ChatRole.user
    )
    # 답변을 모을 버퍼
    full_response = ""
    async for chunk, metadata in agent.astream(
        {"messages": [{"role": "user", "content": request.query}]},
        stream_mode="messages",
        context=Context(space_id=session.space_id),
    ):
        if metadata["langgraph_node"] == "model":
            full_response += chunk.content
        yield f"data: {json.dumps({'token': chunk.content}, ensure_ascii=False)}\n\n"
    new_answer = ChatMessage(
        content=full_response, session_id=session.session_id, role=ChatRole.ai
    )
    asyncio.create_task(save_chat_log([new_question, new_answer]))
    # 스트림 종료 신호 (선택 사항)
    yield "data: [DONE]\n\n"