import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from api import router
from core.config import settings
from errors.base import BackendBaseError
from utils.charset import CharsetMiddleware


app = FastAPI()

app.include_router(router)
app.add_middleware(CharsetMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL], # ⬅️ "*" 대신 명시적 URL 사용
    allow_credentials=True, # ⬅️ ⭐️ 필수!
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
            "message": e.message
        }
    )

@app.exception_handler(Exception)
def exception_handler(_req: Request, e: Exception):
    logging.error(f"Unhandled exception: {e}")

    return JSONResponse(
        status_code=500,
        content={
            "status_code": 500,
            "error_code": "UNKNOWN_ERROR",
            "message": str(e)
        }
    )
