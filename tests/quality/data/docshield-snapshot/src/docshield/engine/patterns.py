"""Regex-based PII pattern detection for structured data.

Complements the GLiNER zero-shot model with deterministic patterns
for structured data types that statistical models often miss:
IBANs, BICs, email addresses, monetary amounts, reference
numbers, tax numbers, URLs, and abbreviated names.
"""

from __future__ import annotations

import re
from typing import NamedTuple


class PatternMatch(NamedTuple):
    text: str
    label: str
    start: int
    end: int


# Patterns ordered from most specific to most generic to reduce false positives.
PATTERNS: dict[str, re.Pattern[str]] = {
    "IBAN": re.compile(
        r"\b[A-Z]{2}\d{2}\s?[A-Z0-9]{4}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{0,4}\d{0,2}\b"
    ),
    "BIC_SWIFT_CODE": re.compile(
        r"\b[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?\b"
    ),
    "EMAIL_ADDRESS": re.compile(
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    ),
    "EURO_AMOUNT": re.compile(
        r"\b\d{1,3}(?:\.\d{3})*,\d{2}\s*Euro\b"
    ),
    "BIRTH_YEAR": re.compile(
        r"(?:Geb\.?\s*(?:jahr|datum|\.)\s*:?\s*)(\d{4})\b", re.IGNORECASE,
    ),
    "ABBREVIATED_NAME": re.compile(
        r"\b([A-Z]\.)\s+([A-ZÄÖÜ][a-zäöüß]{2,})\b"
    ),
    "REFERENCE_NUMBER": re.compile(
        r"\b(?:AR|DE)\d{2,}[A-Z0-9]*\d{4,}\b"
    ),
    "TAX_NUMBER": re.compile(
        r"\b\d{4}\s*/\s*\d{3}\s*/\s*\d{4,5}\b"
    ),
    "WEBSITE_URL": re.compile(
        r"\bwww\.[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"
    ),
    "EMAIL_DOMAIN_REMNANT": re.compile(
        r"(?<=\])@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    ),
    "GERMAN_POSTAL_ADDRESS": re.compile(
        r"\b(\d{5})\s+([A-ZÄÖÜ][a-zäöüß]{2,}(?:\s+[a-zäöüß.]+)*)\b"
    ),
}

# Labels that should capture the regex *group(1)* instead of group(0).
_GROUP1_LABELS = {"BIRTH_YEAR"}

# Surname-like words that the ABBREVIATED_NAME regex should NOT match.
# Imported lazily to avoid circular imports when blocklist grows.
_ABBREV_NAME_REJECT: frozenset[str] | None = None


def _get_abbrev_name_reject() -> frozenset[str]:
    global _ABBREV_NAME_REJECT
    if _ABBREV_NAME_REJECT is None:
        from docshield.engine.blocklist import (
            _COMMON_WORDS_DE,
            _COMMON_WORDS_EN,
            NOT_A_PROPER_NAME,
        )
        _ABBREV_NAME_REJECT = frozenset(
            w.lower()
            for w in (NOT_A_PROPER_NAME | _COMMON_WORDS_EN | _COMMON_WORDS_DE)
        )
    return _ABBREV_NAME_REJECT


def _is_likely_surname(word: str) -> bool:
    """Heuristic: the word after an initial looks like a real surname."""
    if len(word) < 3 or len(word) > 20:
        return False
    reject = _get_abbrev_name_reject()
    return word.lower() not in reject


def detect_patterns(text: str) -> list[PatternMatch]:
    """Find all regex-based PII matches in *text*.

    When two patterns overlap the same span, the one defined earlier in
    ``PATTERNS`` (higher priority) wins.  Returns matches sorted by start
    position descending (right-to-left) for safe in-place replacement.
    """
    raw: list[PatternMatch] = []
    for label, pattern in PATTERNS.items():
        for m in pattern.finditer(text):
            if label in _GROUP1_LABELS and m.lastindex and m.lastindex >= 1:
                raw.append(PatternMatch(
                    text=m.group(1), label=label,
                    start=m.start(1), end=m.end(1),
                ))
            elif label == "ABBREVIATED_NAME":
                surname = m.group(2)
                if not _is_likely_surname(surname):
                    continue
                raw.append(PatternMatch(
                    text=m.group(), label="PERSON_NAME",
                    start=m.start(), end=m.end(),
                ))
            else:
                raw.append(PatternMatch(
                    text=m.group(), label=label,
                    start=m.start(), end=m.end(),
                ))

    # Deduplicate: earlier PATTERNS entries have higher priority.
    priority = {label: idx for idx, label in enumerate(PATTERNS)}
    raw.sort(key=lambda pm: (pm.start, priority.get(pm.label, 999)))

    kept: list[PatternMatch] = []
    occupied_end = -1
    for pm in raw:
        if pm.start < occupied_end:
            continue
        kept.append(pm)
        occupied_end = pm.end

    return sorted(kept, key=lambda pm: pm.start, reverse=True)
