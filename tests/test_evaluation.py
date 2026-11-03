import json
from pathlib import Path

import pytest

from field_agent.evaluation import score_case, summarize
from field_agent.schemas import BlockerCategory, ExtractionResult, Trade

from .conftest import make_result

ROOT = Path(__file__).resolve().parents[1] / "evaluation"


@pytest.mark.parametrize("name,minimum", [("dataset.jsonl", 30), ("holdout.jsonl", 10)])
def test_datasets_are_well_formed(name, minimum):
    cases = [json.loads(line) for line in (ROOT / name).read_text().splitlines() if line.strip()]
    assert len(cases) >= minimum
    assert len({c["id"] for c in cases}) == len(cases)
    for c in cases:
        e = c["expected"]
        assert e["trade"] is None or e["trade"] in Trade.__members__
        assert e["blocker_category"] is None or e["blocker_category"] in BlockerCategory.__members__
        assert isinstance(e["delay_reported"], bool) and isinstance(e["is_blocker"], bool)


CASE = {
    "id": "t",
    "message": "Electrician isn't finished. Probably need another day.",
    "expected": {
        "trade": "electrical",
        "delay_reported": True,
        "is_blocker": True,
        "blocker_category": "predecessor_incomplete",
        "duration_stated": True,
        "project_named": False,
    },
    "injection": False,
}


def test_score_correct_case():
    x = ExtractionResult.model_validate(make_result())
    s = score_case(CASE, x, x, [])
    assert (s.trade_correct, s.delay_correct, s.blocker_correct, s.category_correct) == (True, True, True, True)
    assert s.unsupported_raw == []


def test_score_counts_unsupported_assumptions_against_labels():
    case = {**CASE, "expected": {**CASE["expected"], "duration_stated": False}}
    x = ExtractionResult.model_validate(make_result(project_ref="Oak Hill"))
    s = score_case(case, x, x, [])
    assert s.unsupported_raw == ["estimated_days", "project_ref"]


def test_invalid_output_is_scored_as_schema_failure():
    s = score_case(CASE, None, None, None, error="ExtractionFailed: bad")
    summary = summarize([s])
    assert summary["schema_valid"] == {"correct": 0, "total": 1, "rate": 0.0}
    assert summary["trade_accuracy"]["rate"] is None


def test_dates_are_scored_only_when_labelled():
    x = ExtractionResult.model_validate(make_result(relevant_dates=[{"text": "Thursday", "date": "2026-11-05"}]))
    labelled = {**CASE, "expected": {**CASE["expected"], "dates": {"thursday": "2026-11-05"}}}
    assert score_case(labelled, x, x, []).dates_correct is True
    wrong = {**CASE, "expected": {**CASE["expected"], "dates": {"Thursday": "2026-11-06"}}}
    assert score_case(wrong, x, x, []).dates_correct is False
    assert score_case(CASE, x, x, []).dates_correct is None


def test_conflicts_are_scored_only_when_labelled():
    x = ExtractionResult.model_validate(make_result())
    labelled = {**CASE, "expected": {**CASE["expected"], "conflicts": ["Drywall"]}}
    assert score_case(labelled, x, x, [], conflicts=["Drywall"]).conflicts_correct is True
    assert score_case(labelled, x, x, [], conflicts=[]).conflicts_correct is False
    assert score_case(CASE, x, x, [], conflicts=["Drywall"]).conflicts_correct is None


def test_every_reported_metric_is_documented():
    # evaluation/README.md defines each metric; a new metric must be documented there too.
    doc = (ROOT / "README.md").read_text()
    keys = summarize([]).keys()
    assert [k for k in keys if f"`{k}`" not in doc] == []
