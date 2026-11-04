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
        site message, and this text is logged, sent back in the repair prompt and returned in a 502.

        A forbidden extra key is the one location the model chooses, so it is replaced too."""
        parts = []
        for err in error.errors(include_url=False, include_input=False)[:5]:
            loc = err["loc"]
            if err["type"] == "extra_forbidden":
                loc = (*loc[:-1], "<unexpected field>")
            parts.append(f"{'.'.join(map(str, loc))}: {err['msg']}")
        return cls("; ".join(parts))


class LLMProvider(Protocol):
    name: str
    model: str
    #: Whether a second "repair" call is worthwhile. Deterministic providers say no.
    supports_repair: bool

    def complete(self, system: str, user: str) -> ProviderResult: ...
