from typing import Literal

from chaejeom.llm.base import LLMClient, StructuredOutputError

# Only OpenAI for now; pass base_url to target an OpenAI-compatible server (e.g. vLLM).
Provider = Literal["openai"]


def create_llm(provider: Provider, model: str, **kwargs) -> LLMClient:
    if provider == "openai":
        from chaejeom.llm.openai import OpenAILLM

        return OpenAILLM(model, **kwargs)
    raise ValueError(f"아직 지원하지 않는 LLM 제공자입니다: {provider} (지금은 openai 만 지원)")


__all__ = ["LLMClient", "Provider", "StructuredOutputError", "create_llm"]
