from fastapi import FastAPI

from api import router
from api.exceptions import register_exception_handlers
from core.config import settings
from utils.charset import CharsetMiddleware


app = FastAPI()

app.include_router(router)
app.add_middleware(CharsetMiddleware)
register_exception_handlers(app)
