from fastapi import FastAPI
from utils.env_var import check_env_vars
import core.config

# routers
from api.v1 import router as v1_router

# 필수 환경변수 존재여부 확인
check_env_vars()

app = FastAPI()

app.include_router(v1_router)
