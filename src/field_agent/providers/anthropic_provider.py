"""Claude via the official Anthropic SDK, using structured outputs.

`messages.parse(output_format=ExtractionResult)` sends the Pydantic schema as a JSON-schema
output format, so the model's answer is constrained to that shape and parsed back into the
model. We still re-validate in the pipeline (defence in depth, and the same code path as
every other provider).
"""

from __future__ import annotations

import anthropic
import pydantic

from ..schemas import ExtractionResult
from .base import MalformedOutput, ProviderRefused, ProviderResult, ProviderUnavailable


class AnthropicProvider:
    name = "anthropic"
    supports_repair = True

    def __init__(self, model: str = "claude-opus-5-5", effort: str = "medium", client: anthropic.Anthropic | None = None):
        self.model = model
        self.effort = effort
        # Credentials resolve from ANTHROPIC_API_KEY (or another SDK-supported source).
        self.client = client or anthropic.Anthropic(timeout=60.0, max_retries=2)

    def complete(self, system: str, user: str) -> ProviderResult:
        try:
            response = self.client.messages.parse(
                model=self.model,
                max_tokens=4096,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=ExtractionResult,
                output_config={"effort": self.effort},
            )
        except (anthropic.APIConnectionError, anthropic.RateLimitError, anthropic.InternalServerError) as e:
            raise ProviderUnavailable(type(e).__name__) from e
        except anthropic.AuthenticationError as e:
            raise ProviderUnavailable("authentication failed: check ANTHROPIC_API_KEY") from e
        except anthropic.APIStatusError as e:
            raise ProviderUnavailable(f"API error {e.status_code}") from e
        except pydantic.ValidationError as e:
            # The SDK could not parse the answer into ExtractionResult. Never pass on str(e): it
            # quotes the model's output, which can repeat the message.
            raise MalformedOutput.from_validation_error(e) from e
        except ValueError as e:
            raise MalformedOutput(f"the SDK could not parse the response ({type(e).__name__})") from e

        if response.stop_reason == "refusal":
            raise ProviderRefused("model declined to process this message")
        if response.stop_reason == "max_tokens":
            raise MalformedOutput("response was truncated (max_tokens)")
        text = next((b.text for b in response.content if b.type == "text"), None)
        if not text:
            raise MalformedOutput("no text block in response")
        return ProviderResult(
            text=text,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
