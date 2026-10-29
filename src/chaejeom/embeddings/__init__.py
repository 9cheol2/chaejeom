from chaejeom.embeddings.base import EmbeddingClient
from chaejeom.llm import Provider


def create_embeddings(provider: Provider, model: str, **kwargs) -> EmbeddingClient:
    if provider == "openai":
        from chaejeom.embeddings.openai import OpenAIEmbeddings

        return OpenAIEmbeddings(model, **kwargs)
    raise ValueError(f"아직 지원하지 않는 임베딩 제공자입니다: {provider} (지금은 openai 만 지원)")


__all__ = ["EmbeddingClient", "create_embeddings"]
