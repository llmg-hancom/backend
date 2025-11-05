from fastapi import FastAPI
from .auth import auth_exception_handler
from .health import health_exception_handler


def register_exception_handlers(app: FastAPI):
    auth_exception_handler(app)
    health_exception_handler(app)
