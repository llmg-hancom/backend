from langchain_ollama import ChatOllama, OllamaEmbeddings

from core.config import settings


llm = ChatOllama(
    model="qwen3:30b-instruct",
    validate_model_on_init=True,
    base_url=settings.OLLAMA_BASE_URL,
    temperature=0.2,
    keep_alive="4h",
)
embeddings = OllamaEmbeddings(model="bge-m3:567m", base_url=settings.OLLAMA_BASE_URL)