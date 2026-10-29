from openai import AsyncOpenAI

from chaejeom.embeddings.base import EmbeddingClient
from chaejeom.llm.base import LoopBound


class OpenAIEmbeddings(EmbeddingClient):
    def __init__(self, model: str, base_url: str | None = None, api_key: str | None = None):
        super().__init__(model)
        self._clients = LoopBound(lambda: AsyncOpenAI(base_url=base_url, api_key=api_key))

    @property
    def client(self) -> AsyncOpenAI:
        return self._clients.get()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self.client.embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in sorted(response.data, key=lambda d: d.index)]
