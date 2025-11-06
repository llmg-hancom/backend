from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from errors.health import NotReadyError


def not_ready_error(_req: Request, _e: NotReadyError):
    return JSONResponse(status_code=503, content={"detail": "서비스 준비 중입니다."})


def health_exception_handler(app: FastAPI):
    app.add_exception_handler(NotReadyError, not_ready_error)
