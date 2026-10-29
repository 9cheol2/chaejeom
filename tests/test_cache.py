import asyncio
import json

from fakes import ScriptedLLM

from chaejeom import evaluate
from chaejeom.llm import LLMClient
from chaejeom.schema import Cost, EvalSample

STATEMENTS = json.dumps({"statements": ["진술 1"]}, ensure_ascii=False)
VERDICTS = json.dumps({"statements": [{"statement": "진술 1", "reason": "있음", "verdict": 1}]}, ensure_ascii=False)
SAMPLE = EvalSample(query="질문", contexts=["문맥"], answer="답변")


def _costs(result):
    return [r.cost for s in result.samples for r in s.results]


def test_second_run_reuses_cached_responses(tmp_path):
    llm = ScriptedLLM([STATEMENTS, VERDICTS])

    first = evaluate([SAMPLE], llm, metrics=["ragas.faithfulness"], repeats=1)
    second = evaluate([SAMPLE], llm, metrics=["ragas.faithfulness"], repeats=1)

    assert first.summary[0].mean == second.summary[0].mean == 1.0
    assert _costs(first)[0].llm_calls == 2
    assert _costs(second)[0] == Cost(llm_calls=0, tokens=0, cache_hits=2)
    assert (tmp_path / ".chaejeom_cache" / "llm.sqlite").exists()


def test_cache_off_calls_again():
    llm = ScriptedLLM([STATEMENTS, VERDICTS, STATEMENTS, VERDICTS])

    evaluate([SAMPLE], llm, metrics=["ragas.faithfulness"], cache=False, repeats=1)
    evaluate([SAMPLE], llm, metrics=["ragas.faithfulness"], cache=False, repeats=1)

    assert len(llm.calls) == 4


def test_each_repeat_is_cached_separately():
    llm = ScriptedLLM([STATEMENTS, VERDICTS, STATEMENTS, VERDICTS])

    evaluate([SAMPLE], llm, metrics=["ragas.faithfulness"], repeats=2, concurrency=1)
    again = evaluate([SAMPLE], llm, metrics=["ragas.faithfulness"], repeats=2, concurrency=1)

    assert len(llm.calls) == 4
    assert [c.cache_hits for c in _costs(again)] == [2, 2]


def test_cache_key_includes_model_settings(tmp_path):
    from chaejeom.cache import ResponseCache

    cache = ResponseCache(tmp_path)
    a = ScriptedLLM([STATEMENTS])
    b = ScriptedLLM([STATEMENTS])
    b.temperature = 0.7
    a.cache = b.cache = cache

    asyncio.run(a.complete("프롬프트"))
    asyncio.run(b.complete("프롬프트"))

    assert len(a.calls) == 1 and len(b.calls) == 1


def test_failed_responses_are_not_cached():
    broken = ScriptedLLM(["아님"] * 3)
    first = evaluate([SAMPLE], broken, metrics=["ragas.faithfulness"], repeats=1)

    fixed = ScriptedLLM([STATEMENTS, VERDICTS])
    fixed.cache = broken.cache
    second = evaluate([SAMPLE], fixed, metrics=["ragas.faithfulness"], repeats=1)

    assert first.samples[0].results[0].error is not None
    assert second.summary[0].mean == 1.0
    assert len(fixed.calls) == 2


async def test_variant_keeps_intended_repeats_apart(tmp_path):
    from chaejeom.cache import ResponseCache

    llm = ScriptedLLM(["첫 번째", "두 번째", "세 번째"])
    llm.cache = ResponseCache(tmp_path)

    answers = [await llm.complete("같은 프롬프트", variant=i) for i in range(3)]
    again = [await llm.complete("같은 프롬프트", variant=i) for i in range(3)]

    assert answers == ["첫 번째", "두 번째", "세 번째"]
    assert again == answers
    assert len(llm.calls) == 3


class SlowLLM(LLMClient):
    def __init__(self, max_concurrency: int):
        super().__init__("slow", max_concurrency=max_concurrency)
        self.active = 0
        self.peak = 0

    async def _complete(self, messages, system, json_mode):
        self.active += 1
        self.peak = max(self.peak, self.active)
        await asyncio.sleep(0.01)
        self.active -= 1
        return "응답", 1, 0


async def test_max_concurrency_limits_parallel_calls():
    llm = SlowLLM(max_concurrency=2)

    await asyncio.gather(*(llm.complete(f"프롬프트 {i}") for i in range(6)))

    assert llm.peak == 2
