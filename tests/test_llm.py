import pytest
from fakes import ScriptedLLM
from pydantic import BaseModel

from chaejeom.embeddings import create_embeddings
from chaejeom.llm import StructuredOutputError, create_llm
from chaejeom.llm.base import extract_json
from chaejeom.schema import Cost


class Statements(BaseModel):
    statements: list[str]


@pytest.mark.parametrize(
    "text",
    [
        '{"statements": ["a"]}',
        '```json\n{"statements": ["a"]}\n```',
        '결과입니다.\n{"statements": ["a"]}\n이상입니다.',
    ],
)
def test_extract_json(text):
    assert Statements.model_validate_json(extract_json(text)).statements == ["a"]


async def test_generate_parses_and_counts_cost():
    llm = ScriptedLLM(['{"statements": ["아인슈타인은 독일에서 태어났다."]}'])
    cost = Cost()

    result = await llm.generate("프롬프트", Statements, cost=cost)

    assert result.statements == ["아인슈타인은 독일에서 태어났다."]
    assert cost.llm_calls == 1
    assert cost.tokens == 10


async def test_generate_retries_with_error_feedback():
    llm = ScriptedLLM(['{"wrong": 1}', '{"statements": ["a"]}'])
    cost = Cost()

    result = await llm.generate("프롬프트", Statements, cost=cost)

    assert result.statements == ["a"]
    assert cost.llm_calls == 2
    assert llm.calls[1][-1]["role"] == "user"
    assert "JSON 형식" in llm.calls[1][-1]["content"]


async def test_generate_gives_up_after_max_attempts():
    llm = ScriptedLLM(["아님"] * 3)

    with pytest.raises(StructuredOutputError):
        await llm.generate("프롬프트", Statements)


def test_only_openai_is_supported():
    for provider in ("anthropic", "ollama", "huggingface"):
        with pytest.raises(ValueError, match="openai"):
            create_llm(provider, "model")
        with pytest.raises(ValueError, match="openai"):
            create_embeddings(provider, "model")


async def test_strip_thinking_before_json():
    llm = ScriptedLLM(['<think>진술을 나눠 보자 {"x": 1}</think>\n{"statements": ["a"]}'])

    result = await llm.generate("프롬프트", Statements)

    assert result.statements == ["a"]


class _Capture:
    def __init__(self, response):
        self.kwargs = None
        self.response = response

    async def __call__(self, **kwargs):
        self.kwargs = kwargs
        return self.response


def _openai_response():
    from types import SimpleNamespace

    message = SimpleNamespace(content='{"statements": []}')
    return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=SimpleNamespace(prompt_tokens=3, completion_tokens=2))


async def test_openai_sends_temperature_by_default():
    llm = create_llm("openai", "gpt-4.1-mini", api_key="x")
    capture = _Capture(_openai_response())
    llm.client.chat.completions.create = capture

    await llm.generate("JSON 으로 답하세요", Statements)

    assert capture.kwargs["temperature"] == 0.0
    assert "reasoning_effort" not in capture.kwargs
    assert capture.kwargs["response_format"] == {"type": "json_object"}


async def test_openai_effort_replaces_temperature():
    llm = create_llm("openai", "gpt-5", api_key="x", reasoning_effort="low")
    capture = _Capture(_openai_response())
    llm.client.chat.completions.create = capture

    await llm.generate("JSON 으로 답하세요", Statements)

    assert capture.kwargs["reasoning_effort"] == "low"
    assert "temperature" not in capture.kwargs


def test_clients_construct_without_network():
    assert create_llm("openai", "gpt-4.1-mini", api_key="x").model == "gpt-4.1-mini"
    assert create_llm("openai", "qwen2.5:7b", base_url="http://localhost:8000/v1", api_key="x").client.base_url.host == "localhost"
    assert create_embeddings("openai", "text-embedding-3-large", api_key="x").model == "text-embedding-3-large"


async def test_openai_caps_output_tokens_generously():
    plain = create_llm("openai", "gpt-4.1-mini", api_key="x")
    reasoning = create_llm("openai", "gpt-5", api_key="x", reasoning_effort="low")
    sent = []
    for llm in (plain, reasoning):
        capture = _Capture(_openai_response())
        llm.client.chat.completions.create = capture
        await llm.generate("JSON 으로 답하세요", Statements)
        sent.append({k: v for k, v in capture.kwargs.items() if "max" in k})

    assert sent == [{"max_completion_tokens": 4096}, {"max_completion_tokens": 16000}]
