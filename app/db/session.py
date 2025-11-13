from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Session, create_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from core.config import settings


# settings에서 database_url 프로퍼티 사용
engine = create_engine(
    settings.database_url, echo=(settings.ENVIRONMENT == "development")
)
async_engine = create_async_engine(
    settings.database_url, echo=(settings.ENVIRONMENT == "development")
)


def get_db():
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            raise


async def get_async_db():
    async with AsyncSession(async_engine) as session:
        try:
            yield session
            await session.commit()
        except Exception:
            raise