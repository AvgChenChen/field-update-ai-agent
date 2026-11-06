"""Personal-information handling for logs and storage.

Site messages often contain phone numbers and emails. We store and log a redacted copy,
plus a short fingerprint so the same message can be correlated without keeping its text.
"""

from __future__ import annotations

import hashlib
import re

_EMAIL = re.compile(r"[\w.+%-]+@(?:[\w-]+\.)+[\w-]{2,}")
# North American numbers (optional +1, brackets, dots, dashes or spaces), or any number written
# with a "+" country code, e.g. +44 20 7946 0958. A trailing extension ("ext. 22", "x22") is part
# of the number. Dates (2026-11-02), sizes (2x4) and short ids don't have the 3-3-4 or "+" shape.
_NANP = r"(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}"
_INTERNATIONAL = r"\+\d{1,3}(?:[\s.-]?\d{2,4}){2,5}"
_EXTENSION = r"(?:\s*(?:ext\.?|extension|x)\s*\d{1,5})?"
_PHONE = re.compile(rf"(?<!\w)(?:{_NANP}|{_INTERNATIONAL}){_EXTENSION}(?!\w)", re.IGNORECASE)


def redact(text: str) -> str:
    text = _EMAIL.sub("[email]", text)
    return _PHONE.sub("[phone]", text)


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
