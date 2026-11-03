"""Deterministic date resolution.

Relative dates ("Thursday", "tomorrow", "next week") are resolved in code against the
date the message was received, never left to the model. Models are unreliable at
calendar arithmetic, and a wrong date silently corrupts a schedule.

Rules (documented in the README):
- "today" → received date; "tomorrow" → +1 day.
- A weekday name → the next such day *after* the received date. If the message was
  received on that weekday, "Thursday" means next week's Thursday. "This Thursday" is
  the same as "Thursday".
- "next week" → Monday of the following week (weeks run Monday to Sunday).
- "next Thursday" → Thursday of that following week. Received on Monday Nov 2, "next
  Friday" is Fri Nov 13, not Fri Nov 6; received on Sunday Nov 8, "next Monday" is the
  next day, Mon Nov 9, because a new week starts then.
- "Nov 5" / "November 5" → that date this year, or next year if it would be more
  than 60 days in the past.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MONTHS = {
    m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)
}

DATE_PHRASES = re.compile(
    r"\b(today|tomorrow|next week|(?:(?:next|this)\s+)?(?:mon|tues|wednes|thurs|fri|satur|sun)day"
    r"|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?)\b",
    re.I,
)


def resolve(text: str, received: date) -> date | None:
    t = text.strip().lower()
    if t == "today":
        return received
    if t == "tomorrow":
        return received + timedelta(days=1)
    if t == "next week":
        return received + timedelta(days=7 - received.weekday())
    m = re.fullmatch(r"(next|this)\s+([a-z]+)", t)
    if m and m.group(2) in WEEKDAYS:
        if m.group(1) == "this":
            return resolve(m.group(2), received)
        following_monday = received + timedelta(days=7 - received.weekday())
        return following_monday + timedelta(days=WEEKDAYS.index(m.group(2)))
    if t in WEEKDAYS:
        ahead = (WEEKDAYS.index(t) - received.weekday()) % 7
        return received + timedelta(days=ahead or 7)
    m = re.fullmatch(r"([a-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?", t)
    if m and m.group(1)[:3] in MONTHS:
        try:
            candidate = date(received.year, MONTHS[m.group(1)[:3]], int(m.group(2)))
        except ValueError:
            return None
        if (received - candidate).days > 60:
            candidate = candidate.replace(year=received.year + 1)
        return candidate
    return None


def working_days_between(start: date, end: date) -> int:
    """Working days (Mon-Fri) after `start` up to and including `end`; 0 if end <= start.

    Monday to Thursday is 3 (Tue, Wed, Thu). This is the inverse of
    conflicts.add_working_days for whole days.
    """
    days, d = 0, start
    while d < end:
        d += timedelta(days=1)
        if d.weekday() < 5:
            days += 1
    return days


def find_date_phrases(message: str) -> list[str]:
    """Date phrases in order of appearance, without duplicates."""
    seen: dict[str, None] = {}
    for m in DATE_PHRASES.finditer(message):
        seen.setdefault(m.group(0), None)
    return list(seen)
