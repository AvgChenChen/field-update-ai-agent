"""Provider interface. Every provider returns raw JSON text; the pipeline validates it the same way."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class ProviderResult:
    text: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class ProviderUnavailable(Exception):
    """Network, auth, or rate-limit failure. Not the model's fault; safe to retry later."""


class ProviderRefused(Exception):
    """The model declined to answer."""


class MalformedOutput(Exception):
    """The provider answered, but the answer is not a valid ExtractionResult."""


class LLMProvider(Protocol):
    name: str
    model: str
    #: Whether a second "repair" call is worthwhile. Deterministic providers say no.
    supports_repair: bool

    def complete(self, system: str, user: str) -> ProviderResult: ...
