"""Construction vocabulary shared by the rule-based baseline and the grounding guardrails."""

from __future__ import annotations

import re

from .schemas import Trade

# Words that are evidence a message is about a given trade. Order doesn't matter;
# when several trades appear, the earliest mention wins (it is usually the subject).
TRADE_EVIDENCE: dict[Trade, re.Pattern[str]] = {
    Trade.electrical: re.compile(r"\b(electric(ian|ians|al)?|wiring|wired|panel|gfci|outlets?|breakers?)\b", re.I),
    Trade.plumbing: re.compile(r"\b(plumb(er|ers|ing)|pipes?|drains?|stack|pressure[- ]test(ed)?|water lines?)\b", re.I),
    Trade.drywall: re.compile(r"\b(drywall|sheetrock|tap(e|ed|ing)|mud(ding)?|sand(ing|er)?|hang(ing)? board|5/8)\b", re.I),
    Trade.hvac: re.compile(r"\b(hvac|furnace|duct(s|work)?|air handler|heat pump)\b", re.I),
    Trade.framing: re.compile(r"\b(fram(e|er|ers|ing)|studs?|beams?|blocking|joists?)\b", re.I),
    Trade.concrete: re.compile(r"\b(concrete|pour|slab|footings?|foundation|pump truck)\b", re.I),
    Trade.roofing: re.compile(r"\b(roof(er|ers|ing)?|shingles?)\b", re.I),
    Trade.painting: re.compile(r"\b(paint(er|ers|ing)?|(first|second) coat|primer)\b", re.I),
    Trade.flooring: re.compile(r"\b(floor(ing)? (guys|crew|install)|flooring|hardwood|tile|tiler|carpet|lvp)\b", re.I),
    Trade.insulation: re.compile(r"\b(insulat(ion|ing|e|ed)|spray foam|batts|vapou?r barrier)\b", re.I),
    Trade.demolition: re.compile(r"\b(demo|demolition|dumpster|tear[- ]?out)\b", re.I),
    Trade.finish_carpentry: re.compile(r"\b(cabinets?|millwork|trim|uppers|finish carpentry)\b", re.I),
    Trade.other: re.compile(r"\b(windows?|counter(top)?s?|templated|glass|glazing)\b", re.I),
    Trade.general: re.compile(r"\b(inspect(or|ion)|general contractor|site super)\b", re.I),
}

# Phrases that support a stated delay *duration*. Without one of these, an
# estimated_days value is an unsupported assumption.
DURATION_EVIDENCE = re.compile(
    r"\b(\d+(\.\d+)?|one|two|three|four|five|six|seven|ten|a|an|another|couple( of)?|few|half( a)?)\s+"
    r"(more\s+)?(business\s+|working\s+)?(day|days|week|weeks|hours?)\b"
    r"|\b(tomorrow|tonight|next week|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    re.I,
)

# Openers of a question inside a sentence: "can you check if ...", "ask him whether ...".
# Everything from the opener to the end of the clause is a question, not a statement.
_EMBEDDED_QUESTION = re.compile(
    r"(\b(can|could|would|will)\s+(you|someone|somebody|anyone)\b"
    r"|\b(check|ask|see|find out|confirm|wondering|not sure|unsure)\b[^,;.!?]*?\b(if|whether)\b)"
    r"[^,;]*",
    re.I,
)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def stated_text(message: str) -> str:
    """The parts of a message that state something, with questions removed.

    "Can someone check if they need another day?" asks about a duration; it doesn't give
    one. Direct questions (sentences ending in "?") and embedded ones ("ask whether ...")
    are dropped, so duration evidence is only taken from statements. A plain "if" is kept:
    "if it rains it's another day" still states a duration.
    """
    kept = []
    for sentence in _SENTENCE_END.split(message.strip()):
        if sentence.rstrip().endswith("?"):
            continue
        sentence = " ".join(_EMBEDDED_QUESTION.sub("", sentence).split())
        if sentence.rstrip(" ,;.!"):
            kept.append(sentence)
    return " ".join(kept)


ORDINALS = {"1st": "first", "2nd": "second", "3rd": "third", "4th": "fourth"}
GENERIC_WORDS = {"job", "site", "project", "house", "the", "street", "unit", "home", "residence", "renovation"}


def trade_mentions(text: str) -> list[tuple[int, Trade]]:
    """All trades with evidence in the text, ordered by first mention."""
    hits = []
    for trade, pattern in TRADE_EVIDENCE.items():
        m = pattern.search(text)
        if m:
            hits.append((m.start(), trade))
    return sorted(hits)


def normalise_words(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {ORDINALS.get(w, w) for w in words}
