"""Pydantic models: the contract between the LLM, the API, and downstream systems.

`ExtractionResult` is "ExtractionResult v1" in docs/INTEGRATION.md. Enum values match
the shared vocabulary used by construction-ops-platform and construction-dependency-engine.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Trade(StrEnum):
    general = "general"
    demolition = "demolition"
    concrete = "concrete"
    framing = "framing"
    roofing = "roofing"
    plumbing = "plumbing"
    electrical = "electrical"
    hvac = "hvac"
    insulation = "insulation"
    drywall = "drywall"
    painting = "painting"
    flooring = "flooring"
    finish_carpentry = "finish_carpentry"
    other = "other"


class WorkStatus(StrEnum):
    not_started = "not_started"
    in_progress = "in_progress"
    complete = "complete"
    delayed = "delayed"
    blocked = "blocked"
    unknown = "unknown"


class BlockerCategory(StrEnum):
    predecessor_incomplete = "predecessor_incomplete"
    material = "material"
    inspection = "inspection"
    labor = "labor"
    weather = "weather"
    access = "access"
    design = "design"
    other = "other"
    none = "none"


class Severity(StrEnum):
    none = "none"
    low = "low"
    medium = "medium"
    high = "high"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Delay(_Strict):
    reported: bool = Field(description="True only if the message says work is late or will take longer.")
    estimated_days: float | None = Field(
        default=None, ge=0, le=365, description="Working days of delay, only if the message states or clearly implies a duration."
    )
    reason: str | None = Field(default=None, max_length=300)


class ScheduleImpact(_Strict):
    blocks_downstream: bool = Field(description="True if other work cannot proceed because of this.")
    affected_activities: list[str] = Field(default_factory=list, max_length=10)
    severity: Severity = Severity.none


class Blocker(_Strict):
    is_blocker: bool
    category: BlockerCategory = BlockerCategory.none
    description: str | None = Field(default=None, max_length=300)


class Confidence(_Strict):
    overall: float = Field(ge=0, le=1)
    low_confidence_fields: list[str] = Field(default_factory=list, max_length=20)


_Date = date  # the field below is named "date", which would shadow the type inside the class


class DateMention(_Strict):
    text: str = Field(max_length=60, description="The words in the message, e.g. 'Thursday' or 'tomorrow'.")
    date: _Date | None = Field(default=None, description="Calendar date, resolved against the message's received date.")
    refers_to: str | None = Field(default=None, max_length=120, description="What the date is about, e.g. 'drywall start'.")


class ExtractionResult(_Strict):
    """What the extractor must return. Unknown values are null, never guessed."""

    project_ref: str | None = Field(default=None, max_length=120, description="Project or site named in the message.")
    trade: Trade | None = Field(default=None, description="The trade whose work the update is mainly about.")
    location: str | None = Field(default=None, max_length=120)
    work_status: WorkStatus = WorkStatus.unknown
    delay: Delay
    schedule_impact: ScheduleImpact
    blocker: Blocker
    relevant_dates: list[DateMention] = Field(default_factory=list, max_length=6)
    follow_up_questions: list[str] = Field(default_factory=list, max_length=5)
    missing_information: list[str] = Field(default_factory=list, max_length=10)
    confidence: Confidence
    assumptions: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("follow_up_questions", "missing_information", "assumptions")
    @classmethod
    def _strip_empty(cls, items: list[str]) -> list[str]:
        return [i.strip()[:300] for i in items if i and i.strip()]


# ---------------------------------------------------------------- API models


class ContextTask(BaseModel):
    """An upcoming task from the caller's schedule, used only for conflict detection."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    trade: Trade | None = None
    planned_start: date
    depends_on_trades: list[Trade] = Field(default_factory=list, max_length=10)


class ExtractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4000, description="The raw text of the site update.")
    project_hint: str | None = Field(
        default=None, max_length=120, description="Project the sender is known to be on, if the caller knows it."
    )
    sender_role: str | None = Field(default=None, max_length=60, description="e.g. 'site super', 'electrician'.")
    received_on: date | None = Field(default=None, description="Date the message was received. Defaults to today (UTC).")
    schedule_context: list[ContextTask] = Field(
        default_factory=list, max_length=50, description="Upcoming tasks to check for scheduling conflicts."
    )


class ScheduleConflict(BaseModel):
    task: str
    planned_start: date
    constraint_date: date | None
    explanation: str


class GuardrailReport(BaseModel):
    injection_flags: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    removed_unsupported: list[str] = Field(default_factory=list)
    repair_attempted: bool = False


class ExtractResponse(BaseModel):
    request_id: str
    extraction: ExtractionResult
    guardrails: GuardrailReport
    conflicts: list[ScheduleConflict] = Field(default_factory=list)
    provider: str
    model: str
    latency_ms: int


class ActionType(StrEnum):
    send_follow_up = "send_follow_up"
    record_progress = "record_progress"
    open_issue = "open_issue"
    flag_schedule_risk = "flag_schedule_risk"


class ActionStatus(StrEnum):
    pending_approval = "pending_approval"
    approved = "approved"
    rejected = "rejected"


class ProposedAction(BaseModel):
    id: str
    update_id: str
    type: ActionType
    status: ActionStatus
    summary: str
    payload: dict[str, Any]
    created_at: datetime
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = None


class UpdateRecord(BaseModel):
    id: str
    received_at: datetime
    message_redacted: str
    message_fingerprint: str
    extraction: ExtractionResult
    guardrails: GuardrailReport
    conflicts: list[ScheduleConflict] = Field(default_factory=list)
    provider: str
    model: str
    actions: list[ProposedAction] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reviewer: str = Field(min_length=1, max_length=80, description="Name of the person approving or rejecting.")
    note: str | None = Field(default=None, max_length=500)
