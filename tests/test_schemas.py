import pytest
from pydantic import ValidationError

from field_agent.schemas import ExtractionResult, ExtractRequest

from .conftest import make_result


def test_valid_result_parses():
    r = ExtractionResult.model_validate(make_result())
    assert r.trade == "electrical"
    assert r.delay.estimated_days == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"trade": "carpentry"},  # not in the shared vocabulary
        {"confidence": {"overall": 1.5}},
        {"delay": {"estimated_days": -2}},
        {"blocker": {"category": "aliens"}},
        {"approved": True},  # extra fields are forbidden: the model can't smuggle in an approval
        {"delay": {"reported": True, "estimated_days": 1, "reason": None, "auto_send": True}},
    ],
)
def test_invalid_results_are_rejected(overrides):
    with pytest.raises(ValidationError):
        ExtractionResult.model_validate(make_result(**overrides))


def test_blank_list_items_are_dropped():
    r = ExtractionResult.model_validate(make_result(follow_up_questions=["  ", "When?"], assumptions=[""]))
    assert r.follow_up_questions == ["When?"]
    assert r.assumptions == []


def test_request_limits():
    with pytest.raises(ValidationError):
        ExtractRequest(message="")
    with pytest.raises(ValidationError):
        ExtractRequest(message="x" * 4001)
    with pytest.raises(ValidationError):
        ExtractRequest.model_validate({"message": "hi", "unexpected": 1})
