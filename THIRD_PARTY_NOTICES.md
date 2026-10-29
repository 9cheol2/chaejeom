# Third-Party Notices

Chaejeom's metrics are reimplementations based on the source code of the projects below. Chaejeom does not depend on
these libraries. The Korean prompt translations are treated as derivative works and attributed accordingly.

## Changes common to all ported metrics

- Prompts are translated into Korean, few-shot examples are rewritten in Korean, and inputs and outputs use the
  Chaejeom schema.
- The DeepEval verdict prompts and the TruLens chain-of-thought template gain one line that sets the style of the
  reason text (polite "~습니다" style; `REASON_STYLE` in `src/chaejeom/metrics/style.py`). The judging criteria are
  unchanged.
- JSON format retry: when a response does not match the required JSON format, Chaejeom's LLM client reports the error
  and asks again (not in the originals). This applies to ragas.faithfulness, ragas.response_relevancy and the three
  DeepEval metrics; ragas.context_relevance turns it off and uses only its own upstream `max_retries` loop.
- Calls that expect JSON use the OpenAI JSON object mode (`response_format={"type": "json_object"}`) rather than the
  originals' structured output with an enforced schema.
- DeepEval: verdict responses require `verdicts`, as on the upstream structured-output path used with its default
  model (gpt-4o-mini). A verdict outside the allowed vocabulary (yes/no, plus borderline where applicable) is a format
  error and goes through the retry above; if it still fails, the metric records an error instead of scoring an empty
  verdict list.
- TruLens: instead of the upstream structured output and JSON conversion call, the score is read from a JSON object in
  the response first, then by the upstream text parser (the `Score:` line). The upstream last-resort path, which takes
  the smallest in-range number anywhere in the response, is not used; such a response counts as unreadable. Scale
  notation stripping also handles Korean notations (0~3, 0에서 3 사이, 0부터 3까지 and similar). Responses whose score
  cannot be read are not cached.
- Upstream failure values (NaN in RAGAS, -1.0 in TruLens) are reported as `score=None`.
- Generation settings: non-reasoning models receive only `temperature=0`; `top_p` and `seed` are not sent. The default
  `reasoning_effort` for reasoning models is `low` (upstream TruLens sets `medium`; RAGAS and DeepEval leave the API
  default).
- Output token cap: 4,096 tokens for non-reasoning models and 16,000 for reasoning models (upstream RAGAS uses 1,024;
  DeepEval and TruLens set no cap). Normal verdicts stay under 1,000 tokens; the cap only cuts off runaway JSON output,
  which is then retried as a format error.

Changes specific to a metric are listed at the top of that metric's source file.

| Project | License | Version | Commit | Repository |
|---|---|---|---|---|
| Ragas | Apache-2.0 | v0.4.3 | 4ecab384fda829ca50bec3f07cc49589d756e172 | https://github.com/vibrantlabsai/ragas |
| DeepEval | Apache-2.0 | 4.3.1 | 29dcf5f24397715a60348c1e41e7d416a3b2d6c8 | https://github.com/confident-ai/deepeval |
| TruLens | MIT | 2.16.0 | 1f65a310cd5bdaef3ea7be76e98022f574cea39c | https://github.com/truera/trulens |

None of the three projects has a NOTICE file at the commits above.

---

## Ragas

Copyright 2023 Vibrant Labs

Licensed under the Apache License, Version 2.0. The full text is the same as [LICENSE](LICENSE).

## DeepEval

Copyright 2024 Confident AI Inc.

Licensed under the Apache License, Version 2.0. The full text is the same as [LICENSE](LICENSE).

## TruLens

MIT License

Copyright (c) 2023 Truera, Inc.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
