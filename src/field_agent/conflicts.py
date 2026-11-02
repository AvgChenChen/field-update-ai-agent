"""Schedule-conflict detection against caller-supplied upcoming tasks. Deterministic.

A conflict is an upcoming task that depends on the reported trade and is planned to
start on or before the date the reported work can be relied on. We only use dates the
message supports (a resolved *future* date, or the received date plus a stated delay); if
the delay is open-ended, any dependent task starting within a week is flagged as
"can't be confirmed".
"""

from __future__ import annotations

from datetime import date, timedelta

from .schemas import ContextTask, ExtractionResult, ScheduleConflict

LOOKAHEAD_DAYS = 7


def add_working_days(start: date, n: float) -> date:
    d, remaining = start, int(round(n + 0.49))  # partial days round up
    while remaining > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            remaining -= 1
    return d


def detect_conflicts(x: ExtractionResult, received: date, context: list[ContextTask]) -> list[ScheduleConflict]:
    if not context or x.trade is None or not (x.delay.reported or x.blocker.is_blocker):
        return []
    # Only future dates can say when the work will be done. "Couldn't finish today" mentions
    # today, but means the work runs past today, so dates on or before the received date are
    # not completion constraints (issue #2).
    future = [m.date for m in x.relevant_dates if m.date and m.date > received]
    if future:
        constraint: date | None = max(future)
        basis = f"the message points to {constraint:%a %b %-d}"
    elif x.delay.estimated_days is not None:
        constraint = add_working_days(received, x.delay.estimated_days)
        basis = f"a {x.delay.estimated_days:g}-day delay from {received:%a %b %-d} runs to {constraint:%a %b %-d}"
    else:
        constraint = None
        basis = "the message gives no date for when the work will be done"

    trade = x.trade.value.replace("_", " ")
    conflicts = []
    for task in context:
        if x.trade not in task.depends_on_trades:
            continue
        if constraint is not None and task.planned_start <= constraint:
            conflicts.append(
                ScheduleConflict(
                    task=task.name,
                    planned_start=task.planned_start,
                    constraint_date=constraint,
                    explanation=f"'{task.name}' is planned for {task.planned_start:%a %b %-d} and depends on {trade}, "
                    f"but {basis}.",
                )
            )
        elif constraint is None and (task.planned_start - received).days <= LOOKAHEAD_DAYS:
            conflicts.append(
                ScheduleConflict(
                    task=task.name,
                    planned_start=task.planned_start,
                    constraint_date=None,
                    explanation=f"'{task.name}' starts {task.planned_start:%a %b %-d} and depends on {trade}; "
                    f"its start can't be confirmed because {basis}.",
                )
            )
    return conflicts
