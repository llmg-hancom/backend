from fastapi import FastAPI
from core.config import settings
from api import router
from api.exceptions import register_exception_handlers

app = FastAPI()

app.include_router(router)
register_exception_handlers(app)
