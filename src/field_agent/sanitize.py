"""Input normalisation and prompt-injection detection.

Detection is a *signal*, not the defence. The real defences are structural:
the message is passed to the model as delimited data, the output must match a
fixed schema (it has no field that could approve or send anything), and every
proposed action waits for a person. A message that tries to give orders can at
worst produce a wrong extraction that a human then reviews.
"""

from __future__ import annotations

import re
import unicodedata

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

INJECTION_PATTERNS: dict[str, re.Pattern[str]] = {
    "override_instructions": re.compile(
        r"\b(ignore|disregard|forget|override)\b.{0,40}\b(instructions?|rules|prompt|above|previous|prior)\b", re.I
    ),
    "role_change": re.compile(r"\b(you are now|act as|pretend to be|new role|developer mode|jailbreak)\b", re.I),
    "system_prompt_probe": re.compile(r"\b(system prompt|your instructions|reveal .{0,20}prompt)\b", re.I),
    "auto_approval_request": re.compile(
        r"\b(auto[- ]?approve|approve (it|this|all|everything)|mark (it|this|everything|all)? ?(as )?(approved|complete|done)"
        r"|without (human )?(review|approval))\b",
        re.I,
    ),
    "outbound_action_request": re.compile(
        r"\b(send|text|email|forward)\b.{0,30}\b(to (everyone|all|the client|every)|all (subs|subcontractors|contacts))\b", re.I
    ),
    "delimiter_breakout": re.compile(r"</?\s*(site_message|system|assistant|instructions?)\s*>", re.I),
    "output_format_override": re.compile(
        r"\b(respond|reply|output|return)\b.{0,20}\b(only|exactly|with)\b.{0,20}\b(json|yaml|text)\b", re.I
    ),
}


def normalize(text: str, max_chars: int) -> tuple[str, bool]:
    """NFKC-normalise, drop control characters, collapse whitespace, cap length.

    Returns (clean_text, was_truncated). Truncation is reported, never silent.
    """
    clean = unicodedata.normalize("NFKC", text)
    clean = _CONTROL.sub(" ", clean)
    clean = re.sub(r"[ \t]+", " ", clean).strip()
    truncated = len(clean) > max_chars
    return (clean[:max_chars], truncated)


def detect_injection(text: str) -> list[str]:
    return [name for name, pattern in INJECTION_PATTERNS.items() if pattern.search(text)]


def escape_for_prompt(text: str) -> str:
    """Neutralise anything that looks like our delimiter tags so the message can't close them."""
    return text.replace("<", "‹").replace(">", "›")
