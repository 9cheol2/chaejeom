"""Judge prompts for the Chaejeom metrics.

The judge only marks items; scores come from the rules in ``scoring``. The
templates combine what works in the upstream prompts: atomic statements and
noncommittal answers (RAGAS), unsupported versus contradicted claims (DeepEval),
trivial-sentence filtering, evidence quotes, all-entity relevance and full
coverage of multi-part questions (TruLens).

A domain profile names the service in the role line and adds its rules, word
for word, as a "[이 도메인의 판정 기준]" block that takes precedence over the
procedure (see :func:`with_domain`). A custom template from ``/prompt`` replaces
the template with one rewritten to the user's request (see
``chaejeom.customize.prompt_file``). Either way the "[평가 지표]" line and the
"[출력 형식]" block stay as they are, so results are parsed and scored the same way.

Contexts and answer sentences get prompt-local labels (``c1``, ``s1``) that the
code maps back to the real ids; showing dataset ids made the judge copy the ids
from the output-format example.
"""

import json
import re

from chaejeom.metrics.style import REASON_STYLE

RETRY = """

[다시 확인]
이전 응답에서 다음 번호가 빠졌습니다: {missing}
모든 번호를 빠짐없이 한 번씩 포함해 다시 답하세요."""


def numbered(prefix: str, texts: list[str]) -> str:
    return "\n".join(f"[{prefix}{i}] {text}" for i, text in enumerate(texts, start=1))


def _dump(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


# Few-shot examples use a banking scenario to avoid overlap with evaluation data and mix several verdict values.
_EXAMPLE_QUERY = "정기예금을 중도 해지하면 이자는 어떻게 되나요?"
_EXAMPLE_CONTEXTS = [
    "정기예금을 만기 전에 해지하면 중도해지 이율 연 0.5%가 적용된다.",
    "정기예금은 영업점과 모바일 앱에서 가입할 수 있다.",
    "주택담보대출의 중도상환수수료는 1.2%이다.",
]
_EXAMPLE_SENTENCES = [
    "만기 전에 해지하면 연 1.0%의 중도해지 이율이 적용됩니다.",
    "정기예금은 영업점에서 가입할 수 있고, 해지도 모바일 앱에서 할 수 있습니다.",
    "더 궁금하신 점은 고객센터로 문의해 주세요.",
]

GROUNDEDNESS_EXAMPLE = "\n".join(
    [
        f"질문: {_EXAMPLE_QUERY}",
        "문맥:",
        numbered("c", _EXAMPLE_CONTEXTS[:2]),
        "답변:",
        numbered("s", _EXAMPLE_SENTENCES),
        "출력:",
        _dump(
            {
                "sentences": [
                    {
                        "id": "s1",
                        "statements": [
                            {
                                "statement": "정기예금을 만기 전에 해지하면 연 1.0%의 중도해지 이율이 적용된다.",
                                "core": True,
                                "absence": False,
                                "verdict": "contradicted",
                                "context_id": "c1",
                                "quote": "정기예금을 만기 전에 해지하면 중도해지 이율 연 0.5%가 적용된다.",
                                "reason": "문맥에는 중도해지 이율이 연 0.5%로 되어 있어 답변의 연 1.0%와 어긋납니다.",
                            }
                        ],
                    },
                    {
                        "id": "s2",
                        "statements": [
                            {
                                "statement": "정기예금은 영업점에서 가입할 수 있다.",
                                "core": False,
                                "absence": False,
                                "verdict": "supported",
                                "context_id": "c2",
                                "quote": "정기예금은 영업점과 모바일 앱에서 가입할 수 있다.",
                                "reason": "문맥에 정기예금을 영업점에서 가입할 수 있다고 되어 있습니다.",
                            },
                            {
                                "statement": "정기예금은 모바일 앱에서 해지할 수 있다.",
                                "core": False,
                                "absence": False,
                                "verdict": "unsupported",
                                "context_id": "",
                                "quote": "",
                                "reason": "문맥에는 모바일 앱에서 가입할 수 있다는 내용만 있고 해지 방법은 없습니다.",
                            },
                        ],
                    },
                    {"id": "s3", "statements": []},
                ]
            }
        ),
    ]
)

CONTEXT_RELEVANCE_EXAMPLE = "\n".join(
    [
        f"질문: {_EXAMPLE_QUERY}",
        "문맥:",
        numbered("c", _EXAMPLE_CONTEXTS),
        "출력:",
        _dump(
            {
                "question_target": "정기예금 중도 해지 시 이자",
                "chunks": [
                    {"id": "c1", "about_target": True, "has_answer": True, "reason": "정기예금 중도 해지 시 적용되는 이율을 담고 있습니다."},
                    {"id": "c2", "about_target": True, "has_answer": False, "reason": "같은 정기예금을 다루지만 가입 방법만 담고 있습니다."},
                    {"id": "c3", "about_target": False, "has_answer": False, "reason": "정기예금이 아닌 주택담보대출을 다룹니다."},
                ],
            }
        ),
    ]
)

ANSWER_RELEVANCE_EXAMPLE = "\n".join(
    [
        f"질문: {_EXAMPLE_QUERY}",
        "답변: 만기 전에 해지하면 연 0.5%의 중도해지 이율이 적용됩니다. 참고로 저희 은행은 토요일에도 영업합니다.",
        "출력:",
        _dump(
            {
                "question_target": "정기예금 중도 해지 시 이자",
                "answer_target": "정기예금 중도 해지 시 이자",
                "declines_missing": False,
                "declines_quote": "",
                "evasive": False,
                "same_target": True,
                "discusses_asked": True,
                "answers_directly": True,
                "irrelevant_parts": ["참고로 저희 은행은 토요일에도 영업합니다."],
                "reason": "중도 해지 시 이율을 직접 답했지만, 영업일 안내는 질문과 관계없습니다.",
            }
        ),
    ]
)


GROUNDEDNESS = """당신은 RAG(검색 증강 생성) 시스템의 답변을 평가하는 평가자입니다.

[평가 지표] 근거성: 답변의 내용이 문맥으로 뒷받침되는지 봅니다. 질문에 맞게 답했는지는 보지 않습니다.

[원칙]
- 판단의 근거는 아래에 주어진 내용뿐입니다. 당신이 알고 있는 지식은 근거로 쓰지 마세요.
- 문맥이나 답변의 길이는 판단에 영향을 주지 않습니다.
- 반드시 JSON 만 출력하세요.
- 그럴듯하거나 실제로 맞는 내용이라도 문맥에 없으면 문맥으로 뒷받침되지 않은 것입니다.

[절차]
1. 답변은 문장마다 s1, s2 처럼 번호가 붙어 있습니다. 모든 문장을 빠짐없이 순서대로 검토합니다.
2. 문장마다 그 문장에 담긴 사실 진술을 뽑습니다. 진술 하나에는 사실 하나만 담고, 대명사 없이 그 자체로 이해되게 씁니다.
   진술에는 그 문장에 실제로 쓰인 내용만 담습니다. 문맥의 내용을 진술로 옮겨 적지 마세요.
   인사말, 맺음말, "~에 문의하세요" 같은 일반 안내, "잘 모르겠습니다" 같은 답변 회피에는 사실 진술이 없으므로,
   그 문장의 statements 는 빈 목록으로 둡니다.
   "제공된 자료에서 확인되지 않습니다"처럼 질문이 묻는 정보가 문맥에 없다고 밝히는 문장은 진술로 뽑고 absence 를 true 로 둡니다.
   다른 진술은 absence 가 false 입니다. 다만 안내 문장에 전화번호, 주소, URL, 영업시간, 금액 같은 구체적인 값이 있으면
   그 값을 담은 진술을 뽑습니다(예: "고객센터 전화번호는 1588-0000이다").
3. 진술마다 핵심 여부를 정합니다. 질문이 직접 묻는 정보이거나 그 정보의 조건(수치, 기한, 대상, 금액 등)이면 핵심(core: true),
   그 밖에 덧붙인 정보면 부수(core: false)입니다.
4. 진술마다 문맥과 비교해 판정합니다.
   - supported: 문맥에 같은 내용이 있거나, 문맥에서 바로 추론됩니다.
     표현이 달라도 뜻이 같으면 supported 입니다. 하지만 문맥이 비슷한 주제를 말할 뿐 진술 자체를 뒷받침하지 않으면
     supported 가 아닙니다.
     조각 머리의 날짜와 조각 안의 '지난해', '올해', '이번 분기', '전년' 같은 상대 표현으로 기간을 바로 계산할 수 있으면
     바로 추론된 것입니다(예: '[2026-01-30] 지난해 영업이익'은 2025년 영업이익). 조각 어디에도 기간을 알 수 있는 단서가
     없으면 그 기간의 정보로 보지 않습니다.
   - contradicted: 문맥과 어긋납니다. 수치, 조건, 대상이 문맥과 다른 경우입니다.
   - unsupported: 문맥에 그 내용이 없습니다.
   문맥 조각끼리 내용이 서로 다르면, 진술과 같은 내용의 조각이 하나라도 있을 때 supported 로 보고 그 조각을 근거로 듭니다.
   contradicted 는 진술을 뒷받침하는 조각이 하나도 없고 어긋나는 조각이 있을 때만입니다. 어느 조각이 최신이거나 맞는지는 판단하지 않습니다.
   absence 가 true 인 진술은 답변의 주장을 믿지 말고, 먼저 질문이 묻는 값(기간이 상대 표현으로 적힌 것 포함)이 담긴 문장을
   문맥에서 찾아 quote 에 옮깁니다. 찾았으면 contradicted, 문맥 어디에도 없을 때만 supported(quote 와 context_id 는 빈 문자열)입니다.
5. supported 와 contradicted 는 근거가 된 문장을 문맥에서 글자 그대로 옮겨 quote 에 적고, 그 문맥의 번호(c1, c2 등)를 context_id 에 적습니다.
   supported 의 quote 에는 진술에 나온 수치가 그대로 들어 있어야 합니다. 한 진술의 근거가 여러 조각에 나뉘어 있으면
   진술을 되풀이해 적지 말고, 근거 문장들을 줄을 바꿔 quote 에 모두 옮기고 context_id 에 "c1, c2"처럼 함께 적습니다.
   unsupported 는 quote 와 context_id 를 빈 문자열로 둡니다.
6. reason 에 판정 이유를 한 문장으로 씁니다. {reason_style}

[출력 형식]
{{"sentences": [{{"id": "s1", "statements": [{{"statement": "...", "core": true, "absence": false, "verdict": "supported", "context_id": "c1", "quote": "...", "reason": "..."}}]}}]}}
답변의 모든 문장 번호가 빠짐없이 한 번씩 나와야 합니다.

[예시]
{example}

이제 아래 내용을 판정하세요.

[질문]
{query}

[문맥]
{contexts}

[답변]
{sentences}
"""

CONTEXT_RELEVANCE = """당신은 RAG(검색 증강 생성) 시스템의 답변을 평가하는 평가자입니다.

[평가 지표] 문맥 관련성: 검색된 문맥 조각이 질문과 관련 있는지 봅니다. 답변은 보지 않습니다.

[원칙]
- 판단의 근거는 아래에 주어진 내용뿐입니다. 당신이 알고 있는 지식은 근거로 쓰지 마세요.
- 문맥이나 답변의 길이는 판단에 영향을 주지 않습니다.
- 반드시 JSON 만 출력하세요.

[절차]
1. 질문이 묻는 대상(제도, 상품, 사람, 장소 등)을 question_target 에 적습니다.
2. 문맥 조각마다 아래 질문에 true 또는 false 로 답합니다.
   - about_target: 이 조각이 질문이 묻는 대상을 다루는가? 같은 대상이면 묻는 것과 다른 내용(기한, 절차, 조건 등)이어도 true 입니다.
     예: 예금 금리를 묻는데 같은 예금의 가입 방법을 담은 조각은 true, 대출 금리를 담은 조각은 false.
   - has_answer: 이 조각이 질문이 묻는 것 자체(값, 방법, 가능 여부 등)를 담고 있어 답하는 데 쓸 수 있는가?
     질문이 회사, 기간, 지표처럼 여러 조건을 함께 물으면 그 조건을 모두 만족해야 true 입니다.
     예: 2025년 영업이익을 묻는데 조각에 2024년 영업이익만 있으면 false.
     조각 머리의 날짜와 '지난해', '이번 분기' 같은 상대 표현으로 질문한 기간임을 바로 계산할 수 있으면 true 입니다.
3. reason 에 판단 이유를 한 문장으로 씁니다. {reason_style}
4. 모든 조각을 주어진 순서대로, 조각 번호(c1, c2 등)를 id 로 써서 답합니다.

[출력 형식]
{{"question_target": "...", "chunks": [{{"id": "c1", "about_target": true, "has_answer": true, "reason": "..."}}]}}
모든 조각 번호가 빠짐없이 한 번씩 나와야 합니다.

[예시]
{example}

이제 아래 내용을 판정하세요.

[질문]
{query}

[문맥]
{contexts}
"""

ANSWER_RELEVANCE = """당신은 RAG(검색 증강 생성) 시스템의 답변을 평가하는 평가자입니다.

[평가 지표] 답변 관련성: 답변이 질문이 묻는 것에 답하는지 봅니다. 답변 내용이 사실인지, 문맥에 근거하는지는 보지 않습니다.

[원칙]
- 판단의 근거는 아래에 주어진 내용뿐입니다. 당신이 알고 있는 지식은 근거로 쓰지 마세요.
- 문맥이나 답변의 길이는 판단에 영향을 주지 않습니다.
- 반드시 JSON 만 출력하세요.

[절차]
1. 질문이 묻는 대상(제도, 상품, 사람, 장소 등)을 question_target 에, 답변이 다룬 대상을 answer_target 에 적습니다.
2. 아래 질문에 true 또는 false 로 답합니다.
   - declines_missing: 답변이 질문이 묻는 정보가 주어진 자료(검색 결과)에 없다고 밝히는가?
     "제공된 자료에서 확인되지 않습니다"처럼 밝히면 true 입니다. 이유 없이 "잘 모르겠습니다"라고 하거나 문의처만 안내하면 false 입니다.
     다른 것을 답했을 뿐 자료에 없다고 말하지 않았으면 false 입니다. true 면 그렇게 밝힌 문장을 답변에서 글자 그대로 옮겨
     declines_quote 에 적고, false 면 declines_quote 는 빈 문자열입니다.
   - evasive: 답변이 답을 피하는가? "잘 모르겠습니다"나 문의처 안내만 하는 경우입니다.
     "경우에 따라 다릅니다"처럼 어떤 경우인지 밝히지 않는 모호한 답도 true 입니다. 자료에 없다고 밝힌 경우는 false 입니다.
   - same_target: 답변이 다룬 대상이 질문이 묻는 대상과 같은가? 비슷한 분야라도 다른 제도나 다른 상품이면 false 입니다.
     예: 예금 금리를 물었는데 대출 금리를 답했다면 false.
     답변이 대상을 따로 밝히지 않으면(예: "네, 가능합니다") 질문의 대상에 대한 답으로 읽고 true 입니다.
     질문 대상을 포함하는 더 넓은 대상을 다루면 true 입니다(예: 청년적금을 물었는데 적금 일반을 설명한 경우).
   - discusses_asked: 답변이 질문이 묻는 것(값, 방법, 가능 여부 등)에 대해 말하는가? 구체적인 답이 없어도 그것에 대해 말하면 true 입니다.
     예: 예금의 가입 기간을 물었는데 가입 방법만 말했다면 false.
   - answers_directly: 답변이 질문이 묻는 것을 직접 답하는가?
     질문이 여러 가지를 함께 물으면 모두 직접 답해야 true 입니다. 일부만 답하면 false 입니다.
3. 답변에서 질문과 관계없는 부분을 답변에서 글자 그대로 옮겨 irrelevant_parts 에 모두 적습니다. 없으면 빈 목록입니다.
   인사말과 맺음말은 관계없는 부분으로 보지 않습니다. 질문한 것과 바로 이어지는 보충 정보(같은 상품이나 절차의 다른 조건, 수치,
   주의사항)도 관계없는 부분이 아닙니다. 위치, 행사, 담당 조직처럼 질문과 상관없는 안내만 적습니다.
4. reason 에 판단 이유를 한 문장으로 씁니다. {reason_style}

[출력 형식]
{{"question_target": "...", "answer_target": "...", "declines_missing": false, "declines_quote": "", "evasive": false, "same_target": true, "discusses_asked": true, "answers_directly": true, "irrelevant_parts": [], "reason": "..."}}

[예시]
{example}

이제 아래 내용을 판정하세요.

[질문]
{query}

[답변]
{answer}
"""


def _fill(template: str, example: str) -> str:
    """Inline the example (escaping its JSON braces for ``str.format``) and the reason style."""
    return template.replace("{example}", example.replace("{", "{{").replace("}", "}}")).replace("{reason_style}", REASON_STYLE)


GROUNDEDNESS = _fill(GROUNDEDNESS, GROUNDEDNESS_EXAMPLE)
CONTEXT_RELEVANCE = _fill(CONTEXT_RELEVANCE, CONTEXT_RELEVANCE_EXAMPLE)
ANSWER_RELEVANCE = _fill(ANSWER_RELEVANCE, ANSWER_RELEVANCE_EXAMPLE)

TEMPLATES = {
    "chaejeom.groundedness": GROUNDEDNESS,
    "chaejeom.context_relevance": CONTEXT_RELEVANCE,
    "chaejeom.answer_relevance": ANSWER_RELEVANCE,
}

ROLE = "당신은 RAG(검색 증강 생성) 시스템의 답변을 평가하는 평가자입니다."
DOMAIN_ROLE = "당신은 다음 서비스의 답변을 평가하는 평가자입니다: {service}"
DOMAIN_RULES = """[이 도메인의 판정 기준]
아래 기준이 위 [절차]와 다르면 아래 기준을 따릅니다. 이 기준은 어떻게 판정할지를 정할 뿐, 무엇이 사실인지는 정하지 않습니다.
{rules}"""


def _escape(text: str) -> str:
    return text.replace("{", "{{").replace("}", "}}")


def _bullets(rules: str) -> str:
    """Put each sentence of the rules on its own bullet line, keeping the wording.

    A period after a digit ("1. 기간", "3.5 이상") does not end a sentence.
    """
    sentences = (s.strip().removeprefix("- ") for line in rules.splitlines() for s in re.split(r"(?<=[^\d]\.)\s+", line))
    return "\n".join(f"- {s}" for s in sentences if s)


def with_domain(template: str, service: str, rules: str) -> str:
    """Name the service in the role line and add the rules before the output format, both word for word.

    Code inserts the text rather than an LLM rewriting the prompt: in trials, a rewrite invented rules the user
    never gave and dropped unrelated built-in ones.
    """
    if service:
        template = template.replace(ROLE, DOMAIN_ROLE.format(service=_escape(service)), 1)
    if rules.strip():
        block = DOMAIN_RULES.format(rules=_escape(_bullets(rules)))
        template = template.replace("\n\n[출력 형식]", f"\n\n{block}\n\n[출력 형식]", 1)
    return template


def groundedness(query: str, contexts: list[str], sentences: list[str], template: str | None = None) -> str:
    return (template or GROUNDEDNESS).format(query=query, contexts=numbered("c", contexts), sentences=numbered("s", sentences))


def context_relevance(query: str, contexts: list[str], template: str | None = None) -> str:
    return (template or CONTEXT_RELEVANCE).format(query=query, contexts=numbered("c", contexts))


def answer_relevance(query: str, answer: str, template: str | None = None) -> str:
    return (template or ANSWER_RELEVANCE).format(query=query, answer=answer)


def preview(metric_id: str, template: str | None = None) -> str:
    """Render the judge prompt with ``{query}``-style placeholders for display in ``/prompt``."""
    if metric_id == "chaejeom.groundedness":
        return groundedness("{query}", ["{contexts}"], ["{answer}"], template)
    if metric_id == "chaejeom.context_relevance":
        return context_relevance("{query}", ["{contexts}"], template)
    return answer_relevance("{query}", "{answer}", template)
