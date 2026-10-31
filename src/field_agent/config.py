"""Settings read from environment variables. No secrets have defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    llm_provider: str = "heuristic"
    anthropic_model: str = "claude-opus-5-5"
    anthropic_effort: str = "medium"
    openai_model: str | None = None
    api_key: str | None = None
    database_path: str = "data/agent.db"
    store_raw_messages: bool = False
    max_message_chars: int = 2000

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            llm_provider=os.environ.get("LLM_PROVIDER", "heuristic").strip().lower(),
            anthropic_model=os.environ.get("ANTHROPIC_MODEL", "claude-opus-5-5").strip(),
            anthropic_effort=os.environ.get("ANTHROPIC_EFFORT", "medium").strip(),
            openai_model=(os.environ.get("OPENAI_MODEL") or "").strip() or None,
            api_key=os.environ.get("AGENT_API_KEY") or None,
            database_path=os.environ.get("DATABASE_PATH", "data/agent.db"),
            store_raw_messages=_bool(os.environ.get("STORE_RAW_MESSAGES")),
            max_message_chars=int(os.environ.get("MAX_MESSAGE_CHARS", "2000")),
        )
