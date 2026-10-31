from __future__ import annotations

from ..config import Settings
from .base import LLMProvider
from .heuristic import HeuristicProvider


def build_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "heuristic":
        return HeuristicProvider()
    if settings.llm_provider == "anthropic":
        from .anthropic_provider import AnthropicProvider

        return AnthropicProvider(model=settings.anthropic_model, effort=settings.anthropic_effort)
    if settings.llm_provider == "openai":
        if not settings.openai_model:
            raise ValueError("LLM_PROVIDER=openai needs OPENAI_MODEL set to the model you want to use.")
        from .openai_provider import OpenAIProvider

        return OpenAIProvider(model=settings.openai_model)
    raise ValueError(f"Unknown LLM_PROVIDER {settings.llm_provider!r}. Use 'anthropic', 'openai' or 'heuristic'.")
