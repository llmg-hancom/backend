import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlmodel import Session, SQLModel
from starlette.middleware.cors import CORSMiddleware

from api import router
from core.config import settings
from db.session import engine
from errors.base import BackendBaseError
from utils.charset import CharsetMiddleware
import models  # noqa: F401

# 로깅 설정
if settings.ENVIRONMENT == "development":
    LOG_LEVEL = logging.DEBUG
else:
    LOG_LEVEL = logging.WARNING

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


# lifespan 이벤트를 정의합니다
# noinspection PyTypeChecker
@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 앱 시작 시 실행
    logger.info("Application startup...")
    logger.info("Initializing database...")

    with Session(engine) as session:
        # 1. vector 확장 기능 활성화
        session.exec(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        session.commit()

        # 2. 테이블 생성
        SQLModel.metadata.create_all(engine)

        # 3. 인덱스 생성
        session.exec(
            text("""
                 CREATE INDEX IF NOT EXISTS hnsw_embedding_idx
                     ON document_chunks
                         USING hnsw (embedding vector_cosine_ops)
                     WITH (m = 16, ef_construction = 64);
                 """)
        )
        session.commit()

    logger.info("Database initialization complete.")

    yield  # 이 지점에서 FastAPI 애플리케이션이 실행됩니다.

    # 앱 종료 시 실행
    logger.info("Application shutdown...")


app = FastAPI(lifespan=lifespan)
app.include_router(router)
app.add_middleware(CharsetMiddleware)
# "*" 대신 명시적 URL 사용
origins = [
    "http://localhost",
    "http://localhost:3000",
    settings.FRONTEND_URL,
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,  # 필수!
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(BackendBaseError)
def backend_base_error_handler(_req: Request, e: BackendBaseError):
    return JSONResponse(
        status_code=e.status_code,
        content={
            "status_code": e.status_code,
            "error_code": e.error_code,
            "message": e.message,
        },
    )


@app.exception_handler(Exception)
def exception_handler(_req: Request, e: Exception):
    logging.error(f"Unhandled exception: {e}")

    return JSONResponse(
        status_code=500,
        content={"status_code": 500, "error_code": "UNKNOWN_ERROR", "message": str(e)},
    )
