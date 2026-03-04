"""Human-readable run report output."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from docshield.models import RunResult

logger = logging.getLogger("docshield.reporting")


def print_report(results: Sequence[RunResult]) -> None:
    """Print a formatted table of pipeline results using Rich (with fallback)."""
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        logger.debug("Rich not available, falling back to plain text")
        _print_plain(results)
        return

    console = Console()
    table = Table(title="DocShield Run Report")
    table.add_column("Document")
    table.add_column("Status")
    table.add_column("PII Flags", justify="right")
    table.add_column("Output")
    table.add_column("Error")

    for r in results:
        table.add_row(
            r.document_name,
            r.status,
            str(r.pii_count),
            r.output_file,
            r.error or "",
        )
    console.print(table)

    ok = sum(1 for r in results if r.succeeded)
    logger.info("Report printed: %d/%d succeeded", ok, len(results))


def _print_plain(results: Sequence[RunResult]) -> None:
    for r in results:
        line = f"{r.document_name}: {r.status} (pii={r.pii_count}, output={r.output_file})"
        if r.error:
            line += f" error={r.error}"
        print(line)
