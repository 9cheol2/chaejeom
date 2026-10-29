import asyncio
import contextvars
import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from chaejeom.cache import ResponseCache
from chaejeom.pricing import usd
from chaejeom.schema import Cost

T = TypeVar("T", bound=BaseModel)

Message = dict[str, str]

# Follow-up sent when a response fails JSON validation. This retry is a chaejeom addition;
# the upstream metrics do not have it.
FORMAT_RETRY = "출력이 요구한 JSON 형식과 맞지 않습니다.\n{error}\n형식에 맞는 JSON만 다시 출력하세요."

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


# Running cost of one evaluation (metric x sample x run). Set by evaluate() so the cost already
# spent is still reported when a metric fails midway.
task_cost: contextvars.ContextVar[Cost | None] = contextvars.ContextVar("chaejeom_task_cost", default=None)


class LoopBound:
    """Hold one SDK client per event loop.

    SDK connections are bound to the loop that first used them, so a second ``asyncio.run``
    would fail with "Event loop is closed". The first client is adopted by the first loop that
    uses it, and a new one is created whenever the loop changes. The first client is built
    eagerly so a missing API key fails immediately.
    """

    def __init__(self, factory: Callable[[], object]):
        self._factory = factory
        self._client = factory()
        self._loop: asyncio.AbstractEventLoop | None = None

    def get(self):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return self._client
        if self._loop is None:
            self._loop = loop
        elif self._loop is not loop:
            self._client, self._loop = self._factory(), loop
        return self._client


class StructuredOutputError(Exception):
    pass


def strip_thinking(text: str) -> str:
    """Remove ``<think>...</think>`` blocks that some reasoning models emit in the response body."""
    return _THINK.sub("", text).strip()


def extract_json(text: str) -> str:
    """Extract the JSON payload from a response, tolerating code fences and surrounding prose."""
    fenced = _FENCE.search(text)
    if fenced:
        text = fenced.group(1)
    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    if not starts:
        return text.strip()
    start = min(starts)
    end = max(text.rfind("}"), text.rfind("]"))
    return text[start : end + 1] if end > start else text[start:]


def _targets(cost: Cost | None) -> list[Cost]:
    """Return the cost records to charge: the caller's and the per-evaluation ``task_cost``."""
    task = task_cost.get()
    targets = [cost] if cost is not None else []
    if task is not None and task is not cost:
        targets.append(task)
    return targets


class LLMClient(ABC):
    """Base class for judge LLM clients.

    Args:
        model: Model name.
        temperature: Sampling temperature. Ignored when ``reasoning_effort`` is set, since most
            reasoning models reject it.
        reasoning_effort: Reasoning effort for reasoning models.
        max_attempts: Default attempts for :meth:`generate` when the output fails validation.
        max_concurrency: Upper bound on concurrent API calls through this client, even when a
            single metric fans out many calls.

    When ``cache`` is set, identical requests (model, settings, prompt, run) reuse the stored response.
    """

    def __init__(
        self,
        model: str,
        temperature: float | None = 0.0,
        reasoning_effort: str | None = None,
        max_attempts: int = 3,
        max_concurrency: int = 8,
    ):
        self.model = model
        self.temperature = None if reasoning_effort is not None else temperature
        self.reasoning_effort = reasoning_effort
        self.max_attempts = max_attempts
        self.max_concurrency = max_concurrency
        self.cache: ResponseCache | None = None
        self._semaphore: asyncio.Semaphore | None = None
        self._semaphore_loop: asyncio.AbstractEventLoop | None = None

    @abstractmethod
    async def _complete(
        self, messages: list[Message], system: str | None, json_mode: bool
    ) -> tuple[str, int, int]:
        """Return the response text, input token count, and output token count."""

    def _cache_identity(self) -> dict:
        """Return client-specific settings that affect responses, for the cache key."""
        return {}

    def _limit(self) -> asyncio.Semaphore:
        # A semaphore is bound to its event loop, and every asyncio.run() starts a new one.
        loop = asyncio.get_running_loop()
        if self._semaphore is None or self._semaphore_loop is not loop:
            self._semaphore = asyncio.Semaphore(self.max_concurrency)
            self._semaphore_loop = loop
        return self._semaphore

    async def _call(
        self,
        messages: list[Message],
        system: str | None,
        json_mode: bool,
        cost: Cost | None,
        variant: int,
        store: bool,
    ) -> tuple[str, Callable[[], None]]:
        """Return the response text and a callback that caches it (called immediately if ``store``)."""
        key = None
        if self.cache is not None:
            key = self.cache.make_key(
                client=type(self).__name__,
                model=self.model,
                temperature=self.temperature,
                reasoning_effort=self.reasoning_effort,
                identity=self._cache_identity(),
                system=system,
                messages=messages,
                json_mode=json_mode,
                variant=variant,
            )
            hit = self.cache.get(key)
            if hit is not None:
                for target in _targets(cost):
                    target.cache_hits += 1
                return hit[0], lambda: None

        async with self._limit():
            text, input_tokens, output_tokens = await self._complete(messages, system, json_mode)
        tokens = input_tokens + output_tokens
        for target in _targets(cost):
            target.llm_calls += 1
            target.tokens += tokens
            target.input_tokens += input_tokens
            target.output_tokens += output_tokens
            target.usd += usd(self.model, input_tokens, output_tokens) or 0.0

        def save() -> None:
            if key is not None:
                self.cache.put(key, text, tokens)

        if store:
            save()
        return text, save

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        cost: Cost | None = None,
        variant: int = 0,
        accept: Callable[[str], bool] | None = None,
    ) -> str:
        """Return a free-text completion.

        Args:
            prompt: User message.
            system: Optional system message.
            cost: Cost record to charge.
            variant: Distinct value per call when intentionally sampling the same prompt several
                times, so the cache does not return the same response.
            accept: If given, only responses for which it returns True are cached, so an
                unparseable response is not replayed on the next run.
        """
        text, save = await self._call(
            [{"role": "user", "content": prompt}],
            system,
            json_mode=False,
            cost=cost,
            variant=variant,
            store=accept is None,
        )
        text = strip_thinking(text)
        if accept is not None and accept(text):
            save()
        return text

    async def generate(
        self,
        prompt: str,
        output_model: type[T],
        system: str | None = None,
        cost: Cost | None = None,
        max_attempts: int | None = None,
        variant: int = 0,
    ) -> T:
        """Return a response parsed into ``output_model``.

        On a validation error the error is fed back to the model and the request retried.
        Upstream metrics with their own retry loop call this with ``max_attempts=1``. Only valid
        responses are cached, so a failure is not replayed on the next run.

        Raises:
            StructuredOutputError: If no valid response is received within the attempts.
        """
        attempts = max_attempts or self.max_attempts
        messages: list[Message] = [{"role": "user", "content": prompt}]
        last_error: ValidationError | None = None
        for _ in range(attempts):
            text, save = await self._call(messages, system, json_mode=True, cost=cost, variant=variant, store=False)
            try:
                result = output_model.model_validate_json(extract_json(strip_thinking(text)))
                save()
                return result
            except ValidationError as e:
                last_error = e
                messages = [
                    *messages,
                    {"role": "assistant", "content": text},
                    {"role": "user", "content": FORMAT_RETRY.format(error=e)},
                ]
        raise StructuredOutputError(
            f"{attempts}번 시도했지만 {output_model.__name__} 형식의 응답을 받지 못했습니다."
        ) from last_error
