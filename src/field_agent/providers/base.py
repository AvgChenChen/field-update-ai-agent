"""Provider interface. Every provider returns raw JSON text; the pipeline validates it the same way."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import pydantic


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

    @classmethod
    def from_validation_error(cls, error: pydantic.ValidationError) -> MalformedOutput:
        """Field locations and messages only. str(error) quotes the input values, which can repeat the
        site message, and this text is logged, sent back in the repair prompt and returned in a 502."""
        details = "; ".join(
            f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in error.errors(include_url=False, include_input=False)[:5]
        )
        return cls(details)


class LLMProvider(Protocol):
    name: str
    model: str
    #: Whether a second "repair" call is worthwhile. Deterministic providers say no.
    supports_repair: bool

    def complete(self, system: str, user: str) -> ProviderResult: ...
