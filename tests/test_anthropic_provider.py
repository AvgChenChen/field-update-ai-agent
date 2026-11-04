"""The Anthropic provider is tested against a fake client. No network calls, no API key."""

import json
import logging
from types import SimpleNamespace

import anthropic
import httpx2
import pydantic
import pytest

from field_agent.extraction import ExtractionFailed, Extractor
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


PHONE = "416-555-0199"


def sdk_validation_error() -> pydantic.ValidationError:
    """What the SDK raises when the model's JSON doesn't fit the schema. Like the SDK, it uses
    validate_json, and str() of the error quotes the input, here a phone number from the message."""
    try:
        pydantic.TypeAdapter(ExtractionResult).validate_json(json.dumps({"trade": f"Crew is out, call {PHONE}"}))
    except pydantic.ValidationError as e:
        assert PHONE in str(e)
        return e
    raise AssertionError("expected a ValidationError")


def test_sdk_validation_errors_name_the_fields_without_quoting_the_output():
    client, _ = fake_client(error=sdk_validation_error())
    with pytest.raises(MalformedOutput) as excinfo:
        AnthropicProvider(client=client).complete("s", "u")
    assert PHONE not in str(excinfo.value)
    assert "trade: Input should be" in str(excinfo.value)  # still says what to repair


def test_other_sdk_parse_failures_do_not_quote_the_error():
    client, _ = fake_client(error=ValueError(f"could not parse 'call {PHONE}'"))
    with pytest.raises(MalformedOutput) as excinfo:
        AnthropicProvider(client=client).complete("s", "u")
    assert PHONE not in str(excinfo.value)


@pytest.fixture
def agent_logs(caplog):
    # The app's logging setup stops field_agent propagating to the root logger, so attach directly.
    logger = logging.getLogger("field_agent")
    logger.addHandler(caplog.handler)
    caplog.set_level(logging.DEBUG, logger="field_agent")
    yield caplog
    logger.removeHandler(caplog.handler)


def test_message_text_in_an_sdk_validation_error_reaches_neither_logs_nor_the_error(agent_logs):
    client, _ = fake_client(error=sdk_validation_error())
    with pytest.raises(ExtractionFailed) as excinfo:  # its text becomes the 502 detail
        Extractor(AnthropicProvider(client=client)).extract(f"Crew is out, call {PHONE}")
    assert PHONE not in str(excinfo.value)
    assert "extraction_repair" in {r.getMessage() for r in agent_logs.records}  # the error was logged
    for record in agent_logs.records:
        assert PHONE not in record.getMessage()
        assert PHONE not in json.dumps(record.__dict__, default=str)
