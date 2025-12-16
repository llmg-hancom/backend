from langchain_ollama import ChatOllama, OllamaEmbeddings

from core.config import settings

llm = ChatOllama(
    model="gpt-oss:latest",
    validate_model_on_init=True,
    base_url=settings.OLLAMA_BASE_URL,
    reasoning=True,
    temperature=0.1,
    repeat_penalty=1.2,
    mirostat=2,
    mirostat_tau=5,
    mirostat_eta=0.1,
    keep_alive="4h",
)
embeddings = OllamaEmbeddings(model="bge-m3:567m", base_url=settings.OLLAMA_BASE_URL)
