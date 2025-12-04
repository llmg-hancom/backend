from langchain_ollama import ChatOllama, OllamaEmbeddings

from core.config import settings


llm = ChatOllama(
    model="gpt-oss:latest",
    validate_model_on_init=True,
    base_url=settings.OLLAMA_BASE_URL,
    keep_alive="1h",
)
embeddings = OllamaEmbeddings(model="bge-m3:567m", base_url=settings.OLLAMA_BASE_URL)