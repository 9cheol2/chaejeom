from chaejeom.llm import LLMClient


class ScriptedLLM(LLMClient):
    """LLM client that returns canned responses in order and records each request in ``calls``."""

    def __init__(self, responses: list[str], tokens: int = 10):
        super().__init__("scripted")
        self.responses = list(responses)
        self.tokens = tokens
        self.calls: list[list[dict]] = []

    async def _complete(self, messages, system, json_mode):
        self.calls.append(messages)
        return self.responses.pop(0), self.tokens, 0

    def prompt(self, index: int) -> str:
        return self.calls[index][0]["content"]
