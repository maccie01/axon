"""Markdown post-processing to clean up Docling extraction artifacts.

Runs between PDF extraction and PII sanitization to improve
text quality before NER operates on it.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger("docshield.engine.postprocessor")

_IMAGE_MARKER = "<!-- image -->"

_MAX_FRAGMENT_LEN = 50
_MIN_SENTENCE_WORDS = 4


def _is_diagram_fragment(line: str) -> bool:
    """Heuristic: a line is likely a diagram/flowchart OCR fragment."""
    stripped = line.strip()
    if not stripped:
        return False
    if stripped == _IMAGE_MARKER:
        return False
    if stripped.startswith("#"):
        return False
    if stripped.startswith("|") and stripped.endswith("|"):
        return False
    if len(stripped) > _MAX_FRAGMENT_LEN:
        return False
    words = stripped.split()
    return len(words) < _MIN_SENTENCE_WORDS and not stripped.startswith("- ")


def _clean_image_regions(text: str) -> str:
    """Remove orphaned diagram text fragments near image markers.

    Looks for ``<!-- image -->`` markers and cleans up the short
    fragmented lines around them that are typically garbled OCR output
    from flowcharts and process diagrams.
    """
    lines = text.split("\n")
    result: list[str] = []
    idx = 0

    while idx < len(lines):
        line = lines[idx]

        if _IMAGE_MARKER in line.strip():
            result.append(line)
            idx += 1
            fragments_after = 0
            while idx < len(lines):
                next_line = lines[idx]
                stripped = next_line.strip()
                if not stripped:
                    result.append(next_line)
                    idx += 1
                    continue
                if _is_diagram_fragment(next_line):
                    logger.debug("Removing diagram fragment: %r", stripped)
                    fragments_after += 1
                    idx += 1
                    continue
                break
            if fragments_after:
                logger.debug(
                    "Cleaned %d diagram fragments after image marker",
                    fragments_after,
                )
            continue

        result.append(line)
        idx += 1

    return "\n".join(result)


def _collapse_duplicate_columns(text: str) -> str:
    """Collapse markdown tables where columns are duplicated.

    Detects tables where column 2 (and optionally 3+) contain the
    exact same text as column 1, and collapses them to a single column.
    """
    lines = text.split("\n")
    result: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = stripped.split("|")
            # Remove leading/trailing empty strings from split
            if cells and cells[0] == "":
                cells = cells[1:]
            if cells and cells[-1] == "":
                cells = cells[:-1]
            cells = [c.strip() for c in cells]

            if len(cells) >= 3:
                is_separator = all(set(c) <= {"-", ":", " "} for c in cells)
                if is_separator:
                    result.append(line)
                    continue

                unique_cells: list[str] = []
                seen_content: set[str] = set()
                for cell in cells:
                    normalized = cell.rstrip(".")
                    if normalized not in seen_content or not normalized:
                        unique_cells.append(cell)
                        if normalized:
                            seen_content.add(normalized)

                if len(unique_cells) < len(cells):
                    result.append("| " + " | ".join(unique_cells) + " |")
                    continue

        result.append(line)

    return "\n".join(result)


def _normalize_whitespace(text: str) -> str:
    """Collapse runs of 3+ blank lines into 2."""
    return re.sub(r"\n{4,}", "\n\n\n", text)


def postprocess_markdown(text: str) -> str:
    """Apply all post-processing steps to raw Docling markdown."""
    text = _clean_image_regions(text)
    text = _collapse_duplicate_columns(text)
    text = _normalize_whitespace(text)
    return text
