from datetime import date

import pytest

from field_agent.conflicts import add_working_days, detect_conflicts
from field_agent.dates import find_date_phrases, resolve
from field_agent.guardrails import apply_guardrails
from field_agent.schemas import ContextTask, ExtractionResult, GuardrailReport

from .conftest import make_result

MONDAY = date(2026, 11, 2)
THURSDAY = date(2026, 11, 5)


@pytest.mark.parametrize(
    "text,received,expected",
    [
        ("today", MONDAY, date(2026, 11, 2)),
        ("tomorrow", MONDAY, date(2026, 11, 3)),
        ("Thursday", MONDAY, date(2026, 11, 5)),
        ("thursday", THURSDAY, date(2026, 11, 12)),  # said on a Thursday → next week's
        ("Monday", THURSDAY, date(2026, 11, 9)),
        ("next week", THURSDAY, date(2026, 11, 9)),
        ("Nov 5", MONDAY, date(2026, 11, 5)),
        ("January 8th", MONDAY, date(2027, 1, 8)),
        ("Feb 30", MONDAY, None),
        ("end of the month", MONDAY, None),
    ],
)
def test_resolve_relative_dates(text, received, expected):
    assert resolve(text, received) == expected


def test_find_date_phrases_in_order_without_duplicates():
    msg = "Couldn't finish today. Drywall might wait until Thursday, maybe Thursday afternoon, or Nov 9."
    assert find_date_phrases(msg) == ["today", "Thursday", "Nov 9"]


def test_guardrails_correct_model_date_arithmetic_and_drop_invented_dates():
    raw = ExtractionResult.model_validate(
        make_result(
            relevant_dates=[
                {"text": "Thursday", "date": "2026-11-06", "refers_to": "drywall start"},  # wrong: Thursday is Nov 5
                {"text": "next Tuesday", "date": "2026-11-10", "refers_to": "inspection"},  # not in the message
            ]
        )
    )
    report = GuardrailReport()
    out = apply_guardrails(raw, "Drywall might have to wait until Thursday.", None, report, MONDAY)
    assert [(m.text, m.date) for m in out.relevant_dates] == [("Thursday", THURSDAY)]
    assert any(w.startswith("date_corrected") for w in report.warnings)
    assert any("next Tuesday" in r for r in report.removed_unsupported)


def test_add_working_days_skips_weekends():
    assert add_working_days(date(2026, 11, 6), 1) == date(2026, 11, 9)  # Fri + 1 → Mon
    assert add_working_days(MONDAY, 0.5) == date(2026, 11, 3)  # partial days round up


CONTEXT = [
    ContextTask(name="Drywall 2nd floor", trade="drywall", planned_start=date(2026, 11, 4), depends_on_trades=["electrical"]),
    ContextTask(name="Paint", trade="painting", planned_start=date(2026, 11, 20), depends_on_trades=["drywall"]),
    ContextTask(name="Insulation", trade="insulation", planned_start=date(2026, 11, 16), depends_on_trades=["electrical"]),
]


def test_conflict_when_dependent_task_starts_before_the_stated_date():
    x = ExtractionResult.model_validate(make_result(relevant_dates=[{"text": "Thursday", "date": "2026-11-05"}]))
    conflicts = detect_conflicts(x, MONDAY, CONTEXT)
    assert [c.task for c in conflicts] == ["Drywall 2nd floor"]  # Insulation (Nov 16) is fine; Paint doesn't depend on electrical
    assert conflicts[0].constraint_date == THURSDAY
    assert "Wed Nov 4" in conflicts[0].explanation


def test_conflict_from_estimated_delay_and_open_ended_delays():
    x = ExtractionResult.model_validate(make_result(delay={"estimated_days": 3}))
    assert [c.task for c in detect_conflicts(x, MONDAY, CONTEXT)] == ["Drywall 2nd floor"]  # Mon + 3 working days = Thu
    open_ended = ExtractionResult.model_validate(make_result(delay={"estimated_days": None}))
    conflicts = detect_conflicts(open_ended, MONDAY, CONTEXT)
    assert [c.task for c in conflicts] == ["Drywall 2nd floor"] and conflicts[0].constraint_date is None
    assert "can't be confirmed" in conflicts[0].explanation


def test_no_conflicts_without_a_delay_or_context():
    on_track = ExtractionResult.model_validate(
        make_result(delay={"reported": False, "estimated_days": None}, blocker={"is_blocker": False, "category": "none"})
    )
    assert detect_conflicts(on_track, MONDAY, CONTEXT) == []
    assert detect_conflicts(ExtractionResult.model_validate(make_result()), MONDAY, []) == []


def test_today_is_not_a_completion_date():
    """Regression for issue #2: "couldn't finish today" must still flag tomorrow's dependent task."""
    x = ExtractionResult.model_validate(
        make_result(delay={"estimated_days": None}, relevant_dates=[{"text": "today", "date": "2026-11-02"}])
    )
    tomorrow = [ContextTask(name="Drywall", trade="drywall", planned_start=date(2026, 11, 3), depends_on_trades=["electrical"])]
    conflicts = detect_conflicts(x, MONDAY, tomorrow)
    assert [c.task for c in conflicts] == ["Drywall"]
    assert conflicts[0].constraint_date is None and "can't be confirmed" in conflicts[0].explanation


def test_future_date_still_wins_over_today():
    x = ExtractionResult.model_validate(
        make_result(relevant_dates=[{"text": "today", "date": "2026-11-02"}, {"text": "Thursday", "date": "2026-11-05"}])
    )
    conflicts = detect_conflicts(x, MONDAY, CONTEXT)
    assert conflicts[0].constraint_date == THURSDAY


FRIDAY = date(2026, 11, 6)
SUNDAY = date(2026, 11, 8)


@pytest.mark.parametrize(
    "text,received,expected",
    [
        # The four cases from the task, predicted before running.
        ("next Monday", MONDAY, date(2026, 11, 9)),
        ("Friday", FRIDAY, date(2026, 11, 13)),  # said on a Friday → next week's
        ("tomorrow", date(2026, 11, 30), date(2026, 12, 1)),  # across a month end
        ("Monday", date(2026, 12, 26), date(2026, 12, 28)),  # Saturday, across the year's last weekend
        # "next <day>" is that day in the following Monday-to-Sunday week, like "next week".
        ("next Friday", MONDAY, date(2026, 11, 13)),
        ("next Friday", THURSDAY, date(2026, 11, 13)),
        ("next Monday", SUNDAY, date(2026, 11, 9)),
        # "this <day>" is the same as the bare day name.
        ("this Friday", MONDAY, date(2026, 11, 6)),
        # Month and year ends.
        ("Jan 2", date(2026, 12, 30), date(2027, 1, 2)),
        ("next week", SUNDAY, date(2026, 11, 9)),
    ],
)
def test_resolve_same_weekday_next_and_month_ends(text, received, expected):
    assert resolve(text, received) == expected


def test_next_and_this_stay_attached_to_the_day_name():
    msg = "Electrician is back next Friday, drywall this Thursday."
    assert find_date_phrases(msg) == ["next Friday", "this Thursday"]
