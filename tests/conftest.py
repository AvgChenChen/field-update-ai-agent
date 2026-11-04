import json
import logging

import pytest

from field_agent.schemas import ExtractionResult


def make_result(**overrides) -> dict:
    base = {
        "project_ref": None,
        "trade": "electrical",
        "location": "second floor",
        "work_status": "in_progress",
        "delay": {"reported": True, "estimated_days": 1, "reason": "electrician not finished"},
        "schedule_impact": {"blocks_downstream": True, "affected_activities": ["close walls"], "severity": "medium"},
        "blocker": {"is_blocker": True, "category": "predecessor_incomplete", "description": "walls can't be closed"},
        "follow_up_questions": ["When will the electrician finish the second floor?"],
        "missing_information": ["project"],
        "confidence": {"overall": 0.8, "low_confidence_fields": []},
        "assumptions": [],
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = {**base[key], **value}
        else:
            base[key] = value
    return base


@pytest.fixture
def agent_logs(caplog):
    # The app's logging setup stops field_agent propagating to the root logger, so attach directly.
    logger = logging.getLogger("field_agent")
    logger.addHandler(caplog.handler)
    caplog.set_level(logging.DEBUG, logger="field_agent")
    yield caplog
    logger.removeHandler(caplog.handler)


@pytest.fixture
def valid_json() -> str:
    return json.dumps(make_result())


@pytest.fixture
def valid_result() -> ExtractionResult:
    return ExtractionResult.model_validate(make_result())


BRIEF_MESSAGE = (
    "Hey, the electrician isn't finished with the second floor yet. We won't be able to close the walls "
    "tomorrow. Probably need another day."
)
