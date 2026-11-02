"""Rule-based baseline extractor. No network, no LLM.

It exists for two reasons: the API works offline with no credentials, and the
evaluation has a baseline to compare the LLM against. It is deliberately simple
keyword matching, so it is brittle with negation, sarcasm, and unusual phrasing.
The evaluation report shows where.
"""

from __future__ import annotations

import re

from ..dates import find_date_phrases
from ..schemas import (
    Blocker,
    BlockerCategory,
    Confidence,
    DateMention,
    Delay,
    ExtractionResult,
    ScheduleImpact,
    Severity,
    WorkStatus,
)
from ..vocab import stated_text, trade_mentions
from .base import ProviderResult

_MESSAGE = re.compile(r"<site_message>\n(.*)\n</site_message>", re.S)
_HINT = re.compile(r"^Known project for this sender: (.+)$", re.M)

_DELAY = re.compile(
    r"\b(late|behind|delay(ed)?|push(ed)?|slip(ped)?|another day|more (days?|time)|won'?t (be able|make|finish)"
    r"|not (finished|done)|isn'?t (finished|done)|still (not|hasn'?t|waiting)|called off|didn'?t show|no[- ]show"
    r"|can'?t (get|start|hang|sand|install|order|close)|waiting on|no eta|eta\b|lost|quit|failed"
    r"|adding .{0,15}days?|no (exterior |outside )?work)\b",
    re.I,
)
_BLOCKER = re.compile(
    r"\b(can'?t|cannot|won'?t be able|until|waiting on|blocked|before (we|he|she|they)\b|no (exterior |outside )?work"
    r"|didn'?t show|no[- ]show|quit|failed|called off|damaged|backorder(ed)?|short on)",
    re.I,
)
_CATEGORIES: list[tuple[BlockerCategory, re.Pattern[str]]] = [
    (BlockerCategory.weather, re.compile(r"\b(rain|snow|wind|storm|cold|weather|ice)\b", re.I)),
    (BlockerCategory.inspection, re.compile(r"\b(inspect(or|ion)?|permit|sign off)\b", re.I)),
    (BlockerCategory.labor, re.compile(r"\b(didn'?t show|no[- ]show|quit|short[- ]staffed|sick|crew)\b", re.I)),
    (BlockerCategory.access, re.compile(r"\b(lockbox|access|locked|keys?|can'?t get in(to)?)\b", re.I)),
    (
        BlockerCategory.design,
        re.compile(r"\b(homeowner|client|picked|selection|spec|engineer|architect|drawings|change order)\b", re.I),
    ),
    (
        BlockerCategory.material,
        re.compile(r"\b(deliver(y|ed)?|supplier|backorder(ed)?|short on|damaged|arrived|factory|order)\b", re.I),
    ),
    (
        BlockerCategory.predecessor_incomplete,
        re.compile(r"\b(isn'?t finished|not (done|finished)|until|waiting on|before (we|they)|hooked up)\b", re.I),
    ),
]
_COMPLETE = re.compile(r"\b(done|finished|complete|wrapped( up)?|passed)\b", re.I)
_NEGATED_COMPLETE = re.compile(r"\b(isn'?t|not|hasn'?t|never|won'?t)\s+(\w+\s+)?(done|finished|complete)\b", re.I)
_IN_PROGRESS = re.compile(
    r"(\d+\s*%|\bthrough\b|\bstill\b|\bworking\b|\btaped\b|\bhalfway\b|\bfirst coat\b|\bacclimati[sz]ing\b)", re.I
)
_NOT_STARTED = re.compile(r"\b(didn'?t show|no[- ]show|haven'?t started|not started|quit)\b", re.I)
_DURATION = re.compile(
    r"\b(\d+(?:\.\d+)?|one|two|three|four|five|a|an|another|couple(?: of)?|few|half(?: a)?)\s+(?:more\s+)?(?:business\s+|working\s+)?(day|days|week|weeks)\b",
    re.I,
)
_NUMBER_WORDS = {
    "one": 1,
    "a": 1,
    "an": 1,
    "another": 1,
    "two": 2,
    "couple": 2,
    "couple of": 2,
    "three": 3,
    "few": 3,
    "four": 4,
    "five": 5,
    "half": 0.5,
    "half a": 0.5,
}
_LOCATION = re.compile(
    r"\b((?:\d(?:st|nd|rd|th)|first|second|third|main|upper|lower) floor|basement|ensuite|kitchen|garage|laundry"
    r"|addition|bedrooms?|hallway|stair|attic|both floors|upstairs)\b",
    re.I,
)
_PROJECT = re.compile(
    r"\b(?:at|on|for)\s+(?:the\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:St|Street|Ave|Avenue|Rd|Road|Crescent|Drive|Lane))?)\b"
)
_NOT_PROJECTS = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "SYSTEM"}
_ACTIVITIES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"close (the )?walls|close up", re.I), "close walls (insulation and drywall)"),
    (re.compile(r"\bhang\b", re.I), "drywall hanging"),
    (re.compile(r"\bsand\b", re.I), "drywall sanding"),
    (re.compile(r"\border\b", re.I), "material ordering"),
    (re.compile(r"\binstall\b", re.I), "installation"),
    (re.compile(r"sign off|inspection", re.I), "inspection sign-off"),
    (re.compile(r"exterior work", re.I), "exterior work"),
]


def _estimate_days(text: str) -> float | None:
    m = _DURATION.search(stated_text(text))  # a duration only asked about isn't one
    if not m:
        return None
    raw, unit = m.group(1).lower(), m.group(2).lower()
    value = float(raw) if raw[0].isdigit() else float(_NUMBER_WORDS.get(raw, 1))
    return value * 5 if unit.startswith("week") else value


def extract(message: str, project_hint: str | None) -> ExtractionResult:
    mentions = trade_mentions(message)
    specific = [t for _, t in mentions if t.value != "general"]
    trade = specific[0] if specific else (mentions[0][1] if mentions else None)

    delay_reported = bool(_DELAY.search(message))
    is_blocker = bool(_BLOCKER.search(message))
    category = BlockerCategory.none
    if is_blocker:
        category = next((c for c, p in _CATEGORIES if p.search(message)), BlockerCategory.other)

    if _NEGATED_COMPLETE.search(message) or _IN_PROGRESS.search(message):
        status = WorkStatus.in_progress
    elif _NOT_STARTED.search(message):
        status = WorkStatus.not_started
    elif _COMPLETE.search(message):
        status = WorkStatus.complete
    elif is_blocker:
        status = WorkStatus.blocked
    elif delay_reported:
        status = WorkStatus.delayed
    else:
        status = WorkStatus.unknown

    estimated = _estimate_days(message) if delay_reported else None
    loc = _LOCATION.search(message)
    proj = next((m.group(1) for m in _PROJECT.finditer(message) if m.group(1) not in _NOT_PROJECTS), None)
    activities = [label for pattern, label in _ACTIVITIES if pattern.search(message)] if is_blocker else []

    severity = Severity.none
    if is_blocker:
        severity = Severity.high if (estimated is None or estimated >= 3) else Severity.medium
    elif delay_reported:
        severity = Severity.low

    missing: list[str] = []
    questions: list[str] = []
    if not proj and not project_hint:
        missing.append("project")
        questions.append("Which project or site is this about?")
    if trade is None:
        missing.append("trade")
        questions.append("Which trade or crew is this about?")
    if delay_reported and estimated is None:
        missing.append("delay duration")
        questions.append("How many working days do you expect this to add?")
    if is_blocker:
        questions.append("What needs to happen to clear this, and who is handling it?")
    if status is WorkStatus.unknown:
        missing.append("work status")

    confidence = max(0.2, 0.6 - 0.15 * len(missing))
    return ExtractionResult(
        project_ref=proj,
        trade=trade,
        location=loc.group(1) if loc else None,
        work_status=status,
        delay=Delay(reported=delay_reported, estimated_days=estimated, reason=None),
        schedule_impact=ScheduleImpact(
            blocks_downstream=is_blocker and (bool(activities) or category is BlockerCategory.predecessor_incomplete),
            affected_activities=activities,
            severity=severity,
        ),
        blocker=Blocker(is_blocker=is_blocker, category=category, description=None),
        # Dates are left unresolved here; the guardrails resolve them against the received date.
        relevant_dates=[DateMention(text=t, date=None, refers_to=None) for t in find_date_phrases(message)][:6],
        follow_up_questions=questions[:3],
        missing_information=missing,
        confidence=Confidence(overall=round(confidence, 2), low_confidence_fields=[]),
        assumptions=["Rule-based baseline: keyword matching, not language understanding."],
    )


class HeuristicProvider:
    name = "heuristic"
    model = "keyword-rules-v1"
    supports_repair = False

    def complete(self, system: str, user: str) -> ProviderResult:
        m = _MESSAGE.search(user)
        message = m.group(1) if m else user
        hint = _HINT.search(user)
        result = extract(message, hint.group(1) if hint else None)
        return ProviderResult(text=result.model_dump_json(), model=self.model)
