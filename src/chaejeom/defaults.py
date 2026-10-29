# Follows domain-specific judging rules more reliably than gpt-4o-mini.
DEFAULT_JUDGE = {"provider": "openai", "model": "gpt-4.1-mini"}
# LLM verdicts vary slightly even on identical input, so scores are reported as mean ± std over runs.
DEFAULT_RUNS = 3
DEFAULT_EMBEDDING = {"provider": "openai", "model": "text-embedding-3-large"}
# Model for organizing domain descriptions and rewriting judge prompts (/domain, /prompt), configured separately from
# the judge. It makes only a few calls, so favor instruction-following over cost.
DEFAULT_DOMAIN_MODEL = {"provider": "openai", "model": "gpt-4.1-mini"}

# Models offered by the interactive CLI's /model and /embedding (OpenAI only for now).
# Standard models take temperature (default 0), reasoning models reasoning_effort (default low);
# the two are mutually exclusive.
JUDGE_MODELS: dict[str, dict] = {
    "gpt-4o-mini": {"reasoning": False},
    "gpt-4.1-mini": {"reasoning": False},
    "gpt-5-mini": {"reasoning": True},
    "gpt-5.4-mini": {"reasoning": True},
    "gpt-5.6-luna": {"reasoning": True},
    "gpt-6-luna": {"reasoning": True},
}
EMBEDDING_MODELS = ("text-embedding-3-small", "text-embedding-3-large")
REASONING_EFFORTS = ("low", "medium", "high")
# Output token caps. Valid verdicts stay under ~1,000 tokens; the cap cuts off degenerate JSON
# (endless whitespace or symbols) early, and the truncated response is retried as a format error.
# Reasoning models count hidden reasoning tokens against the cap, hence the larger limit.
MAX_OUTPUT_TOKENS = 4096
MAX_OUTPUT_TOKENS_REASONING = 16000
DEFAULT_REASONING_EFFORT = "low"
