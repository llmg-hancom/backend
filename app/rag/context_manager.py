from contextlib import asynccontextmanager

from sqlmodel.ext.asyncio.session import AsyncSession

from db.session import async_engine


# --- DB 세션 관리를 위한 비동기 컨텍스트 매니저 ---
@asynccontextmanager
async def get_db_session():
    async with AsyncSession(async_engine) as session:
        try:
            yield session
            await session.commit()
        except Exception:
            raise