"""The Anthropic provider is tested against a fake client. No network calls, no API key."""

from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from field_agent.providers.anthropic_provider import AnthropicProvider
from field_agent.providers.base import MalformedOutput, ProviderRefused, ProviderUnavailable
from field_agent.schemas import ExtractionResult


class FakeMessages:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.kwargs = response, error, None

    def parse(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.response


def fake_client(**kw):
    messages = FakeMessages(**kw)
    return SimpleNamespace(messages=messages), messages


def response(stop_reason="end_turn", text='{"x": 1}'):
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=[SimpleNamespace(type="text", text=text)] if text else [],
        model="claude-opus-5-5",
        usage=SimpleNamespace(input_tokens=900, output_tokens=200),
    )


def test_calls_structured_outputs_with_the_pydantic_schema():
    client, messages = fake_client(response=response())
    result = AnthropicProvider(model="claude-opus-5-5", effort="medium", client=client).complete("sys", "user")
    assert result.text == '{"x": 1}' and result.model == "claude-opus-5-5"
    assert messages.kwargs["output_format"] is ExtractionResult
    assert messages.kwargs["model"] == "claude-opus-5-5"
    assert messages.kwargs["output_config"] == {"effort": "medium"}
    assert messages.kwargs["system"] == "sys"


def test_refusal_is_surfaced():
    client, _ = fake_client(response=response(stop_reason="refusal", text=None))
    with pytest.raises(ProviderRefused):
        AnthropicProvider(client=client).complete("s", "u")


def test_truncated_output_is_malformed():
    client, _ = fake_client(response=response(stop_reason="max_tokens"))
    with pytest.raises(MalformedOutput, match="truncated"):
        AnthropicProvider(client=client).complete("s", "u")


def test_connection_errors_become_provider_unavailable():
    error = anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages"))
    client, _ = fake_client(error=error)
    with pytest.raises(ProviderUnavailable):
        AnthropicProvider(client=client).complete("s", "u")


def test_sdk_parse_failures_become_malformed_output():
    client, _ = fake_client(error=ValueError("could not parse"))
    with pytest.raises(MalformedOutput):
        AnthropicProvider(client=client).complete("s", "u")
