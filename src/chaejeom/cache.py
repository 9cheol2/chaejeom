import contextvars
import hashlib
import json
import sqlite3
from pathlib import Path

DEFAULT_CACHE_DIR = ".chaejeom_cache"

# Part of the cache key, so each repeated run gets a fresh verdict instead of a cached one.
current_run: contextvars.ContextVar[int] = contextvars.ContextVar("chaejeom_run", default=1)


class ResponseCache:
    """SQLite-backed LLM response cache keyed by model, settings, full prompt, and run number."""

    def __init__(self, directory: str | Path = DEFAULT_CACHE_DIR):
        self.path = Path(directory) / "llm.sqlite"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.execute("CREATE TABLE IF NOT EXISTS responses (key TEXT PRIMARY KEY, text TEXT, tokens INTEGER)")
        self._conn.commit()

    @staticmethod
    def make_key(**parts) -> str:
        payload = json.dumps({**parts, "run": current_run.get()}, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(self, key: str) -> tuple[str, int] | None:
        row = self._conn.execute("SELECT text, tokens FROM responses WHERE key = ?", (key,)).fetchone()
        return (row[0], row[1]) if row else None

    def put(self, key: str, text: str, tokens: int) -> None:
        self._conn.execute("INSERT OR REPLACE INTO responses VALUES (?, ?, ?)", (key, text, tokens))
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
