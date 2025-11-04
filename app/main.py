from fastapi import FastAPI
from core.config import settings

# routers
from api.v1 import router as v1_router

app = FastAPI()

app.include_router(v1_router)
