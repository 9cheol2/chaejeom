from typing import Any

from openai import AsyncOpenAI

from chaejeom.defaults import MAX_OUTPUT_TOKENS, MAX_OUTPUT_TOKENS_REASONING
from chaejeom.llm.base import LLMClient, LoopBound, Message


class OpenAILLM(LLMClient):
    """Client for OpenAI and OpenAI-compatible servers (e.g. vLLM).

    Args:
        model: Model name.
        base_url: API base URL; defaults to OpenAI.
        api_key: API key; defaults to the SDK's environment lookup.
        max_retries: SDK-level retries on 429, 5xx, and connection errors.
        max_output_tokens: Output token cap. Defaults to ``MAX_OUTPUT_TOKENS`` or
            ``MAX_OUTPUT_TOKENS_REASONING``. Not part of the cache key: it only truncates
            degenerate responses, never valid verdicts.
        **kwargs: Passed to :class:`LLMClient`.
    """

    def __init__(
        self,
        model: str,
        base_url: str | None = None,
        api_key: str | None = None,
        max_retries: int = 5,
        max_output_tokens: int | None = None,
        **kwargs,
    ):
        super().__init__(model, **kwargs)
        if max_output_tokens is None:
            max_output_tokens = MAX_OUTPUT_TOKENS_REASONING if self.reasoning_effort is not None else MAX_OUTPUT_TOKENS
        self.max_output_tokens = max_output_tokens
        self._clients = LoopBound(lambda: AsyncOpenAI(base_url=base_url, api_key=api_key, max_retries=max_retries))

    @property
    def client(self) -> AsyncOpenAI:
        return self._clients.get()

    def _cache_identity(self) -> dict:
        return {"base_url": str(self.client.base_url)}

    async def _complete(
        self, messages: list[Message], system: str | None, json_mode: bool
    ) -> tuple[str, int, int]:
        if system:
            messages = [{"role": "system", "content": system}, *messages]
        params: dict[str, Any] = {}
        if self.reasoning_effort is not None:
            params["reasoning_effort"] = self.reasoning_effort
        elif self.temperature is not None:
            params["temperature"] = self.temperature
        if json_mode:
            params["response_format"] = {"type": "json_object"}
        if self.max_output_tokens:
            params["max_completion_tokens"] = self.max_output_tokens
        response = await self.client.chat.completions.create(
            model=self.model, messages=messages, **params
        )
        usage = response.usage
        input_tokens, output_tokens = (usage.prompt_tokens, usage.completion_tokens) if usage else (0, 0)
        return response.choices[0].message.content or "", input_tokens, output_tokens

