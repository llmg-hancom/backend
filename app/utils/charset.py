from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class CharsetMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # Content-Type이 application/json인 경우 charset 추가
        if response.headers.get("content-type") == "application/json":
            response.headers["content-type"] = "application/json; charset=utf-8"

        return response
