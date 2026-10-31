"""The OpenAI provider is tested against a fake client. No network calls, no API key."""

from types import SimpleNamespace

import httpx
import openai
import pytest

from field_agent.config import Settings
from field_agent.providers.base import MalformedOutput, ProviderRefused, ProviderUnavailable
from field_agent.providers.factory import build_provider
from field_agent.providers.openai_provider import OpenAIProvider


class FakeCompletions:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.kwargs = response, error, None

    def create(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.response


def fake(response=None, error=None):
    completions = FakeCompletions(response, error)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions)), completions


def response(content='{"x": 1}', finish_reason="stop", refusal=None):
    message = SimpleNamespace(content=content, refusal=refusal)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason=finish_reason)],
        model="test-model",
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )


def test_uses_json_mode_and_sends_the_schema():
    client, completions = fake(response())
    result = OpenAIProvider(model="test-model", client=client).complete("SYSTEM", "USER")
    assert result.text == '{"x": 1}'
    assert completions.kwargs["response_format"] == {"type": "json_object"}
    assert completions.kwargs["model"] == "test-model"
    system = completions.kwargs["messages"][0]["content"]
    assert system.startswith("SYSTEM") and '"relevant_dates"' in system


@pytest.mark.parametrize(
    "resp,exc",
    [
        (response(content=None, refusal="I can't help with that"), ProviderRefused),
        (response(finish_reason="length"), MalformedOutput),
        (response(content=""), MalformedOutput),
    ],
)
def test_bad_responses(resp, exc):
    client, _ = fake(resp)
    with pytest.raises(exc):
        OpenAIProvider(model="m", client=client).complete("s", "u")


def test_connection_errors_become_provider_unavailable():
    client, _ = fake(error=openai.APIConnectionError(request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions")))
    with pytest.raises(ProviderUnavailable):
        OpenAIProvider(model="m", client=client).complete("s", "u")


def test_factory_requires_an_explicit_openai_model():
    with pytest.raises(ValueError, match="OPENAI_MODEL"):
        build_provider(Settings(llm_provider="openai"))
