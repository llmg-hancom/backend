from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from api import router
from api.exceptions import register_exception_handlers
from core.config import settings
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
register_exception_handlers(app)
