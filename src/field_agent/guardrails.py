"""Deterministic checks applied to every extraction, whatever produced it.

LLM output is treated as untrusted. These checks remove values the message doesn't
support (rather than letting a guessed project name or delay estimate flow into a
schedule) and record everything they change, so a reviewer can see why.
"""

from __future__ import annotations

from datetime import date

from .dates import resolve
from .schemas import ExtractionResult, GuardrailReport
from .vocab import DURATION_EVIDENCE, GENERIC_WORDS, TRADE_EVIDENCE, normalise_words

LOW_CONFIDENCE_THRESHOLD = 0.5


def _mentions_missing(items: list[str], word: str) -> bool:
    return any(word in i.lower() for i in items)


def apply_guardrails(
    result: ExtractionResult, message: str, project_hint: str | None, report: GuardrailReport, received: date | None = None
) -> ExtractionResult:
    r = result.model_copy(deep=True)
    received = received or date.today()
    words = normalise_words(message)
    low = set(r.confidence.low_confidence_fields)

    # 1. A delay duration needs evidence in the text ("another day", "Thursday", "2 weeks").
    if r.delay.estimated_days is not None and not DURATION_EVIDENCE.search(message):
        report.removed_unsupported.append(f"delay.estimated_days={r.delay.estimated_days:g} (no duration in message)")
        r.delay.estimated_days = None
        if not _mentions_missing(r.missing_information, "duration"):
            r.missing_information.append("delay duration")

    # 2. A project reference must come from the message or the caller's hint, never be invented.
    if r.project_ref:
        ref_words = {w for w in normalise_words(r.project_ref) if w not in GENERIC_WORDS and len(w) >= 3}
        hint_words = normalise_words(project_hint or "")
        if ref_words and not (ref_words & (words | hint_words)):
            report.removed_unsupported.append(f"project_ref={r.project_ref!r} (not in message or hint)")
            r.project_ref = None
    if r.project_ref is None and project_hint:
        r.project_ref = project_hint
    if r.project_ref is None and not _mentions_missing(r.missing_information, "project"):
        r.missing_information.append("project")

    # 3. A trade with no supporting words in the message is flagged, not silently trusted.
    if r.trade is not None:
        pattern = TRADE_EVIDENCE.get(r.trade)
        if r.trade.value != "other" and (pattern is None or not pattern.search(message)):
            report.warnings.append(f"unsupported_trade: {r.trade.value} has no supporting words in the message")
            low.add("trade")
            r.confidence.overall = min(r.confidence.overall, 0.5)

    # 4. Location should be grounded too (with "2nd" == "second" normalisation).
    if r.location:
        loc_words = {w for w in normalise_words(r.location) if len(w) >= 3 and w != "floor"}
        if loc_words and not (loc_words & words):
            report.warnings.append(f"unsupported_location: {r.location!r}")
            low.add("location")

    # 5. Dates: the words must be in the message, and relative dates are recomputed in code.
    kept = []
    for mention in r.relevant_dates:
        if mention.text.strip().lower() not in message.lower():
            report.removed_unsupported.append(f"relevant_dates: {mention.text!r} (not in message)")
            continue
        resolved = resolve(mention.text, received)
        if resolved is not None:
            if mention.date is not None and mention.date != resolved:
                report.warnings.append(f"date_corrected: {mention.text!r} {mention.date.isoformat()} -> {resolved.isoformat()}")
            mention.date = resolved
        elif mention.date is not None:
            low.add("relevant_dates")  # a date we can't verify by rule, e.g. "end of the month"
        kept.append(mention)
    r.relevant_dates = kept

    # 6. Messages that try to instruct the system get lower confidence and a visible warning.
    if report.injection_flags:
        report.warnings.append("possible_prompt_injection: instructions in the message were treated as data")
        r.confidence.overall = min(r.confidence.overall, 0.6)

    # 7. Gaps without questions: make sure a reviewer has something to send.
    if r.missing_information and not r.follow_up_questions:
        r.follow_up_questions.append("Could you confirm the " + ", ".join(r.missing_information[:3]) + "?")

    r.confidence.overall = max(0.0, min(1.0, r.confidence.overall))
    r.confidence.low_confidence_fields = sorted(low)
    if r.confidence.overall < LOW_CONFIDENCE_THRESHOLD:
        report.warnings.append("low_confidence: needs human review before use")
    return r


def count_unsupported(result: ExtractionResult, message: str) -> list[str]:
    """Used by the evaluation: which values in a *raw* extraction lack support in the message."""
    problems = []
    if result.delay.estimated_days is not None and not DURATION_EVIDENCE.search(message):
        problems.append("estimated_days")
    if result.project_ref:
        ref = {w for w in normalise_words(result.project_ref) if w not in GENERIC_WORDS and len(w) >= 3}
        if ref and not (ref & normalise_words(message)):
            problems.append("project_ref")
    if result.trade is not None and result.trade.value != "other":
        pattern = TRADE_EVIDENCE.get(result.trade)
        if pattern is None or not pattern.search(message):
            problems.append("trade")
    return problems
