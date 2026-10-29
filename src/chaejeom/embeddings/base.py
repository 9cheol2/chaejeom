from abc import ABC, abstractmethod


class EmbeddingClient(ABC):
    def __init__(self, model: str):
        self.model = model

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
