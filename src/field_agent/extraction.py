"""The extraction pipeline: sanitise → prompt → provider → validate (→ one repair) → guardrails."""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

import pydantic

from .conflicts import detect_conflicts
from .guardrails import apply_guardrails
from .prompts import SYSTEM_PROMPT, build_repair_prompt, build_user_prompt
from .providers.base import LLMProvider, MalformedOutput
from .redact import fingerprint
from .sanitize import detect_injection, normalize
from .schemas import ContextTask, ExtractionResult, GuardrailReport, ScheduleConflict

log = logging.getLogger("field_agent")


class ExtractionFailed(Exception):
    """The provider never produced a valid result. We return an error rather than a guess."""


@dataclass
class ExtractionOutcome:
    request_id: str
    message: str
    raw: ExtractionResult  # what the provider returned, after schema validation
    final: ExtractionResult  # after guardrails
    report: GuardrailReport
    provider: str
    model: str
    latency_ms: int
    received: date
    conflicts: list[ScheduleConflict] = field(default_factory=list)


def _validate(text: str) -> ExtractionResult:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise MalformedOutput(f"not valid JSON: {e.msg} at position {e.pos}") from e
    try:
        return ExtractionResult.model_validate(data)
    except pydantic.ValidationError as e:
        details = "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors()[:5])
        raise MalformedOutput(details) from e


class Extractor:
    def __init__(self, provider: LLMProvider, max_message_chars: int = 2000):
        self.provider = provider
        self.max_message_chars = max_message_chars

    def extract(
        self,
        message: str,
        project_hint: str | None = None,
        sender_role: str | None = None,
        received_on: date | None = None,
        schedule_context: list[ContextTask] | None = None,
    ) -> ExtractionOutcome:
        request_id = uuid.uuid4().hex[:16]
        received = received_on or datetime.now(UTC).date()
        started = time.perf_counter()
        clean, truncated = normalize(message, self.max_message_chars)
        if not clean:
            raise ValueError("message is empty after normalisation")
        report = GuardrailReport(injection_flags=detect_injection(clean))
        if truncated:
            report.warnings.append(f"message_truncated: only the first {self.max_message_chars} characters were analysed")

        user_prompt = build_user_prompt(clean, project_hint, sender_role, received)
        result = self.provider.complete(SYSTEM_PROMPT, user_prompt)
        try:
            raw = _validate(result.text)
        except MalformedOutput as first_error:
            if not self.provider.supports_repair:
                raise ExtractionFailed(str(first_error)) from first_error
            report.repair_attempted = True
            log.warning("extraction_repair", extra={"request_id": request_id, "error": str(first_error)[:200]})
            result = self.provider.complete(SYSTEM_PROMPT, build_repair_prompt(user_prompt, str(first_error)))
            try:
                raw = _validate(result.text)
            except MalformedOutput as second_error:
                raise ExtractionFailed(f"invalid output after one repair attempt: {second_error}") from second_error

        final = apply_guardrails(raw, clean, project_hint, report, received)
        conflicts = detect_conflicts(final, received, schedule_context or [])
        latency_ms = int((time.perf_counter() - started) * 1000)
        # Log metadata only: a fingerprint and length, never the message text.
        log.info(
            "extraction_ok",
            extra={
                "request_id": request_id,
                "message_fingerprint": fingerprint(clean),
                "message_chars": len(clean),
                "provider": self.provider.name,
                "latency_ms": latency_ms,
                "injection_flags": report.injection_flags,
                "removed_unsupported": len(report.removed_unsupported),
                "repair_attempted": report.repair_attempted,
            },
        )
        return ExtractionOutcome(
            request_id, clean, raw, final, report, self.provider.name, result.model, latency_ms, received, conflicts
        )
