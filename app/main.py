from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from psycopg import InternalError
from sqlalchemy import text
from sqlmodel import Session, SQLModel
from starlette.middleware.cors import CORSMiddleware

from api import router
from core.config import settings
from db.session import engine
from errors.base import BackendBaseError
import models  # noqa: F401
from utils.charset import CharsetMiddleware

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
        session.exec(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
        session.commit()
        if settings.ENVIRONMENT == "development":
            try:
                session.exec(
                    text("""CREATE OR REPLACE FUNCTION immutable_array_to_string(arr TEXT[], sep TEXT)
                        RETURNS TEXT AS
                    $$
                    SELECT ARRAY_TO_STRING(arr, sep);
                    $$ LANGUAGE sql IMMUTABLE
                                    PARALLEL SAFE""")
                )
                session.commit()
            except InternalError as e:
                # "tuple concurrently updated" 에러라면 무시
                if "tuple concurrently updated" in str(e):
                    session.rollback()
                    print("Function already created by another worker. Skipping.")
                else:
                    raise e  # 다른 에러면 예외 발생
        session.commit()

        # 2. 테이블 생성
        SQLModel.metadata.create_all(engine)

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
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=[
        "Content-Type",  # 요청의 데이터 타입
        "Accept",  # 응답받을 데이터 타입
        "Authorization",  # Bearer 토큰 사용 대비
        "X-Requested-With",  # AJAX 요청 식별
    ],
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
