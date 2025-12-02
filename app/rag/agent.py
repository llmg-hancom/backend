import asyncio
import json
import logging

from langchain.agents import create_agent

from models import ChatSession
from rag.context_manager import get_db_session
from rag.model import llm
from models.chat_message import ChatRole, ChatMessage
from rag.tools import (
    search_public_law,
    search_private_documents,
    search_precedent,
    Context,
    search_precedent_by_case_number,
)
from schemas.chat import ChatRequest


logger = logging.getLogger(__name__)


def agent_generator(include_law: bool = False, include_precedent: bool = False):
    tools = [search_private_documents]
    prompt = """You are a helpful assistant specialized in Korean law,
        and answers questions about private documents users uploaded using RAG."""
    if include_law:
        tools.append(search_public_law)
        prompt += "\nYou can search for Korean public law using 'search_public_law'."
    if include_precedent:
        tools.append(search_precedent)
        tools.append(search_precedent_by_case_number)
        prompt += (
            "\nYou can search for Korean precedents using 'search_precedent'"
            "and 'search_precedent_by_case_number'."
            "Always use 'search_precedent_by_case_number' when searching by '사건번호',"
            "since searching with '사건번호' in 'search_precedent' will not return intended results."
        )
    prompt += "\nBe concise and accurate"
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