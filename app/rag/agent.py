import asyncio
import json
import logging

from langchain.agents import create_agent

from rag.context_manager import get_db_session
from rag.model import llm
from models.chat_message import ChatRole, ChatMessage
from rag.tools import search_public_law
from schemas.chat import ChatRequest


logger = logging.getLogger(__name__)


agent = create_agent(
    model=llm,
    tools=[search_public_law],
    system_prompt="You are a helpful assistant specialized in Korean law. Be concise and accurate. You can search for korean public law using search_public_law if needed.",
)


async def save_chat_log(chats: list[ChatMessage]):
    try:
        async with get_db_session() as session:
            session.add_all(chats)
        logger.info("[CHAT] 채팅 로그 저장 성공")
    except Exception as e:
        logger.error(f"[CHAT] 채팅 로그 저장 실패: {e}")


# SSE 생성기 (Async Generator)
async def event_generator(session_id: int, request: ChatRequest):
    """
    1. 토큰을 클라이언트에게 실시간 전송 (SSE)
    2. 동시에 전체 답변을 full_response에 조립
    3. 완료 시 DB 저장
    """
    new_question = ChatMessage(
        content=request.query, session_id=session_id, role=ChatRole.user
    )
    # 답변을 모을 버퍼
    full_response = ""
    async for message in agent.astream(
        {"messages": [{"role": "user", "content": request.query}]},
        stream_mode="messages",
    ):
        full_response += message[0].content
        yield f"data: {json.dumps({'token': message[0].content}, ensure_ascii=False)}\n\n"
    new_answer = ChatMessage(
        content=full_response, session_id=session_id, role=ChatRole.ai
    )
    asyncio.create_task(save_chat_log([new_question, new_answer]))
    # 스트림 종료 신호 (선택 사항)
    yield "data: [DONE]\n\n"