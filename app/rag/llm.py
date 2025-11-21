from langchain_ollama import ChatOllama
from core.config import settings

model = ChatOllama(
    model="gpt-oss:latest",
    validate_model_on_init=True,
    base_url=settings.OLLAMA_BASE_URL,
    keep_alive="1h",
)
