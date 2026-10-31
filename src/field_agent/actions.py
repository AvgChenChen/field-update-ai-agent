"""Turn an extraction into *proposed* actions.

Actions are derived by code from validated fields, never from free text the model
wrote, and every action starts as pending_approval. There is no code path that
approves an action except a person calling the review endpoint.
"""

from __future__ import annotations

from typing import Any

from .schemas import ActionType, ExtractionResult, ScheduleConflict


def propose_actions(
    x: ExtractionResult, conflicts: list[ScheduleConflict] | None = None
) -> list[tuple[ActionType, str, dict[str, Any]]]:
    actions: list[tuple[ActionType, str, dict[str, Any]]] = []
    trade = x.trade.value if x.trade else None
    who = trade.replace("_", " ") if trade else "unspecified trade"

    if x.trade and x.work_status.value != "unknown":
        actions.append(
            (
                ActionType.record_progress,
                f"Record {who} as {x.work_status.value.replace('_', ' ')}",
                {
                    "project_ref": x.project_ref,
                    "trade": trade,
                    "location": x.location,
                    "work_status": x.work_status.value,
                    "source": "ai_agent",
                },
            )
        )
    if x.blocker.is_blocker:
        actions.append(
            (
                ActionType.open_issue,
                f"Open a blocking issue ({x.blocker.category.value.replace('_', ' ')}) for {who}",
                {
                    "project_ref": x.project_ref,
                    "trade": trade,
                    "category": x.blocker.category.value,
                    "description": x.blocker.description,
                    "severity": x.schedule_impact.severity.value,
                    "affected_activities": x.schedule_impact.affected_activities,
                },
            )
        )
    if x.delay.reported:
        actions.append(
            (
                ActionType.flag_schedule_risk,
                f"Check schedule impact of the {who} delay"
                + (f" of {x.delay.estimated_days:g} working day(s)" if x.delay.estimated_days is not None else ""),
                {
                    "project_ref": x.project_ref,
                    "trade": trade,
                    "estimated_days": x.delay.estimated_days,
                    # Shape of the request a reviewer could send to construction-dependency-engine once the task is matched.
                    "conflicts": [c.model_dump(mode="json") for c in conflicts or []],
                    "dependency_engine_request": {
                        "endpoint": "POST /v1/schedules/delay-impact",
                        "task_id": None,
                        "delay_days": x.delay.estimated_days,
                    },
                },
            )
        )
    if x.follow_up_questions:
        actions.append(
            (
                ActionType.send_follow_up,
                "Ask the sender: " + " ".join(x.follow_up_questions[:3]),
                {
                    "questions": x.follow_up_questions[:3],
                    "audience": "sender",
                    "draft_message": "Thanks for the update. " + " ".join(x.follow_up_questions[:3]),
                },
            )
        )
    for c in (conflicts or [])[:3]:
        actions.append(
            (
                ActionType.send_follow_up,
                f"Warn the crew for '{c.task}' that its start may move",
                {
                    "audience": f"crew for {c.task}",
                    "task": c.task,
                    "planned_start": c.planned_start.isoformat(),
                    "draft_message": f"Heads up: '{c.task}' is planned for {c.planned_start:%A %b %-d}, but the {who} work it "
                    f"depends on isn't confirmed complete. Please hold until we confirm the start date.",
                },
            )
        )
    return actions
