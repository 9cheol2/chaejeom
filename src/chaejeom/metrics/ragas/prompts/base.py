# Adapted from ragas v0.4.3 (Apache-2.0), commit 4ecab384fda829ca50bec3f07cc49589d756e172
# src/ragas/prompt/metrics/base_prompt.py (BasePrompt.to_string, _generate_examples)
# Changes:
#   - Template text translated to Korean.
#   - Output schema serialised with ensure_ascii=False so Korean field
#     descriptions are not \u-escaped.
#   - adapt() (automatic prompt translation) is not ported.

import json
from typing import ClassVar, Generic, TypeVar

from pydantic import BaseModel

InputModel = TypeVar("InputModel", bound=BaseModel)
OutputModel = TypeVar("OutputModel", bound=BaseModel)


class RagasPrompt(Generic[InputModel, OutputModel]):
    """RAGAS judge prompt: instruction, output JSON schema, few-shot examples, then the input.

    Pydantic docstrings and field descriptions on `output_model` become part of
    the rendered schema, so editing them changes the prompt.
    """

    input_model: ClassVar[type[BaseModel]]
    output_model: ClassVar[type[BaseModel]]
    instruction: ClassVar[str]
    examples: ClassVar[list[tuple[BaseModel, BaseModel]]] = []

    def to_string(self, data: InputModel) -> str:
        output_schema = json.dumps(self.output_model.model_json_schema(), ensure_ascii=False)
        examples_str = self._generate_examples()
        input_json = data.model_dump_json(indent=4, exclude_none=True)

        return f"""{self.instruction}
다음 JSON Schema 를 따르는 JSON 형식으로 출력하세요:
{output_schema}응답에 작은따옴표를 쓰지 말고, 백슬래시로 올바르게 이스케이프한 큰따옴표를 쓰세요.

{examples_str}
-----------------------------

이제 다음 입력에 대해 같은 작업을 수행하세요
입력: {input_json}
출력: """

    def _generate_examples(self) -> str:
        if not self.examples:
            return ""

        example_strings = [
            f"예시 {idx + 1}\n"
            f"입력: {input_data.model_dump_json(indent=4)}\n"
            f"출력: {output_data.model_dump_json(indent=4)}"
            for idx, (input_data, output_data) in enumerate(self.examples)
        ]
        return "--------예시-----------\n" + "\n\n".join(example_strings)
