from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


def not_implemented_error(_req: Request, _e: NotImplementedError):
    return JSONResponse(
        status_code=501, content={"detail": "아직 구현되지 않은 기능입니다."}
    )


def something_wrong(_req: Request, _e: Exception):
    return JSONResponse(
        status_code=500, content={"detail": "알 수 없는 오류가 발생했습니다."}
    )


def general_exception_handler(app: FastAPI):
    app.add_exception_handler(NotImplementedError, not_implemented_error)
    app.add_exception_handler(Exception, something_wrong)
