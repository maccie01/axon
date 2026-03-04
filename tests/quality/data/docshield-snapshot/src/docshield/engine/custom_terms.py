"""Load user-defined custom terms for forced PII masking.

The custom-terms file is a plain-text file (one term per line).
An optional label can be appended after a ``|`` separator.
Lines starting with ``#`` and blank lines are ignored.

Example file::

    # Company names
    Beispiel AG
    Beispiel Digital|COMPANY_NAME
    Beispiel Holding GmbH & Co. KG
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("docshield.engine.custom_terms")

DEFAULT_LABEL = "COMPANY_NAME"


def load_custom_terms(path: Path | None) -> list[tuple[str, str]]:
    """Parse the custom-terms file and return ``(term, NORMALISED_LABEL)`` pairs.

    Returns an empty list when *path* is ``None`` or the file does not exist.
    Terms are returned longest-first so that replacements are greedy.
    """
    if path is None or not path.exists():
        return []

    terms: list[tuple[str, str]] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        if "|" in line:
            term, _, label = line.partition("|")
            term = term.strip()
            label = label.strip().upper().replace(" ", "_")
        else:
            term = line
            label = DEFAULT_LABEL

        if not term:
            logger.warning("Empty term on line %d of %s, skipping", lineno, path)
            continue

        terms.append((term, label))

    terms.sort(key=lambda t: len(t[0]), reverse=True)
    logger.info("Loaded %d custom term(s) from %s", len(terms), path)
    return terms
