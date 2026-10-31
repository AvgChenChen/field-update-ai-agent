"""OpenAI via the official `openai` SDK (optional install: pip install -e ".[openai]").

Uses Chat Completions in JSON mode. JSON mode guarantees syntactically valid JSON but
not our schema, so the schema is included in the system prompt and the pipeline
validates and repairs exactly as for every other provider.

The model must be named explicitly with OPENAI_MODEL; there is no default, so the code
doesn't silently depend on a model name that may be retired.
"""

from __future__ import annotations

import json

from ..schemas import ExtractionResult
from .base import MalformedOutput, ProviderRefused, ProviderResult, ProviderUnavailable


class OpenAIProvider:
    name = "openai"
    supports_repair = True

    def __init__(self, model: str, client=None):
        import openai

        self._openai = openai
        self.model = model
        self.client = client or openai.OpenAI(timeout=60.0, max_retries=2)  # key from OPENAI_API_KEY
        self._schema = json.dumps(ExtractionResult.model_json_schema())

    def complete(self, system: str, user: str) -> ProviderResult:
        oa = self._openai
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": f"{system}\nReturn JSON that validates against this JSON Schema:\n{self._schema}",
                    },
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
                max_completion_tokens=4096,
            )
        except (oa.APIConnectionError, oa.APITimeoutError, oa.RateLimitError, oa.InternalServerError) as e:
            raise ProviderUnavailable(type(e).__name__) from e
        except oa.AuthenticationError as e:
            raise ProviderUnavailable("authentication failed: check OPENAI_API_KEY") from e
        except oa.APIStatusError as e:
            raise ProviderUnavailable(f"API error {e.status_code}") from e

        choice = response.choices[0]
        if getattr(choice.message, "refusal", None):
            raise ProviderRefused("model declined to process this message")
        if choice.finish_reason == "length":
            raise MalformedOutput("response was truncated (max tokens)")
        if not choice.message.content:
            raise MalformedOutput("empty response")
        usage = response.usage
        return ProviderResult(
            text=choice.message.content,
            model=response.model,
            input_tokens=usage.prompt_tokens if usage else None,
            output_tokens=usage.completion_tokens if usage else None,
        )
