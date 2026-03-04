"""Closed-loop restoration of masked PII flags in LLM output."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("docshield.restore")


def build_master_vault(mapping_dir: Path) -> dict[str, str]:
    """Merge all per-document vault JSON files into a single lookup.

    Malformed or unreadable files are logged and skipped so that one
    corrupt vault does not abort the entire restore.
    """
    master: dict[str, str] = {}
    files = sorted(mapping_dir.glob("*.json"))

    if not files:
        logger.warning("No vault JSON files in %s", mapping_dir)
        return master

    for fp in files:
        try:
            raw = fp.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Skipping malformed vault file %s: %s", fp.name, exc)
            continue

        if not isinstance(data, dict):
            logger.warning("Skipping %s: expected dict, got %s", fp.name, type(data).__name__)
            continue

        for key, value in data.items():
            if isinstance(key, str) and isinstance(value, str):
                master[key] = value

    logger.info("Master vault built: %d entries from %d file(s)", len(master), len(files))
    return master


def _normalize_escaped_flags(text: str) -> str:
    """Un-escape backslash-escaped underscores inside flag brackets.

    LLMs in LaTeX/Markdown contexts often emit ``[PERSON\\_NAME\\_FLAG\\_1]``
    instead of ``[PERSON_NAME_FLAG_1]``.  This normalizes them so vault
    look-ups succeed.
    """
    import re

    def _unescape(m: re.Match[str]) -> str:
        return m.group(0).replace(r"\_", "_")

    return re.sub(r"\[[A-Z][A-Z_\\]+FLAG[_\\]+\d+\]", _unescape, text)


def restore_text(text: str, vault: dict[str, str], *, bold: bool = False) -> str:
    """Replace flag tokens with their original values.

    Longer flags are replaced first to prevent partial collisions.
    Escaped underscores (``\\_``) inside flag brackets are normalized first.
    """
    restored = _normalize_escaped_flags(text)
    for flag in sorted(vault, key=len, reverse=True):
        replacement = f"**{vault[flag]}**" if bold else vault[flag]
        restored = restored.replace(flag, replacement)
    return restored


def collect_llm_files(llm_dir: Path) -> list[Path]:
    """Return text/markdown files in *llm_dir*, sorted by name."""
    if not llm_dir.exists():
        return []
    return sorted(
        f for f in llm_dir.iterdir()
        if f.is_file() and not f.name.startswith(".")
    )


@dataclass
class RestoreResult:
    source: str
    output: str
    flags_restored: int
    chars: int


def restore_file(
    input_path: Path,
    output_dir: Path,
    vault: dict[str, str],
    *,
    bold: bool = True,
) -> RestoreResult:
    """Restore a single LLM response file, writing to *output_dir*."""
    text = input_path.read_text(encoding="utf-8")
    restored = restore_text(text, vault, bold=bold)
    out_path = output_dir / f"RESTORED_{input_path.name}"
    out_path.write_text(restored, encoding="utf-8")
    logger.info("Restored %s -> %s (%d flags)", input_path.name, out_path.name, len(vault))
    return RestoreResult(
        source=input_path.name,
        output=out_path.name,
        flags_restored=len(vault),
        chars=len(text),
    )


def run_restorer(
    mapping_dir: Path = Path("mapping"),
    input_path: Path = Path("llm_responses"),
    output_dir: Path = Path("output"),
    *,
    bold: bool = True,
) -> int:
    """CLI-facing entry point for the restore workflow.

    *input_path* can be a single file or a directory of LLM responses.
    """
    vault = build_master_vault(mapping_dir)
    if not vault:
        logger.error("No vault mappings found in %s", mapping_dir)
        return 1

    if input_path.is_dir():
        files = collect_llm_files(input_path)
        if not files:
            logger.warning("No files in %s", input_path)
            return 0
        for fp in files:
            restore_file(fp, output_dir, vault, bold=bold)
        return 0

    if not input_path.exists():
        logger.warning("%s does not exist.", input_path)
        return 1

    text = input_path.read_text(encoding="utf-8")
    if not text.strip():
        logger.warning("%s is empty.", input_path)
        return 0

    out_path = output_dir / f"RESTORED_{input_path.name}"
    restored = restore_text(text, vault, bold=bold)
    out_path.write_text(restored, encoding="utf-8")
    logger.info("Restored output written to %s", out_path)
    return 0
