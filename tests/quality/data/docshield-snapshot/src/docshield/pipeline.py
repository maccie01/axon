"""Document processing pipeline orchestration."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from docshield.engine.postprocessor import postprocess_markdown
from docshield.models import RunResult

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from docshield.engine.extractor import DocumentExtractor
    from docshield.engine.sanitizer import IntelligentSanitizer

logger = logging.getLogger("docshield.pipeline")

PDF_EXTENSIONS = {".pdf"}


def collect_pdfs(input_dir: Path) -> list[Path]:
    """Collect PDF files with case-insensitive extension matching."""
    return sorted(
        f for f in input_dir.iterdir()
        if f.is_file() and f.suffix.lower() in PDF_EXTENSIONS
    )


# Backward-compatible alias used by existing tests
_collect_pdfs = collect_pdfs


def ensure_directories(paths: Iterable[Path]) -> None:
    for p in paths:
        p.mkdir(parents=True, exist_ok=True)


def process_documents(
    input_dir: Path,
    output_dir: Path,
    mapping_dir: Path,
    extractor: DocumentExtractor,
    sanitizer: IntelligentSanitizer,
    on_progress: Callable[[RunResult], None] | None = None,
    on_start: Callable[[str], None] | None = None,
) -> list[RunResult]:
    """Run the extraction + post-processing + sanitization pipeline."""
    files = collect_pdfs(input_dir)
    if not files:
        logger.warning("No PDFs found in %s", input_dir)
        return []

    logger.info("Processing %d PDF(s) from %s", len(files), input_dir)
    results: list[RunResult] = []

    for pdf in files:
        if on_start:
            on_start(pdf.name)
        try:
            raw_markdown = extractor.pdf_to_markdown(pdf)
            markdown = postprocess_markdown(raw_markdown)
            sanitized, vault = sanitizer.sanitize(markdown)

            out_file = output_dir / f"CLEAN_{pdf.stem}.md"
            out_file.write_text(sanitized, encoding="utf-8")

            map_file = mapping_dir / f"VAULT_{pdf.stem}.json"
            map_file.write_text(
                json.dumps(vault, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            result = RunResult(
                document_name=pdf.name,
                output_file=out_file.name,
                pii_count=len(vault),
                status="success",
            )
            logger.info(
                "OK  %s -> %s (%d PII)", pdf.name, out_file.name, len(vault),
            )

        except Exception as exc:  # noqa: BLE001
            logger.error("FAIL %s: %s", pdf.name, exc)
            result = RunResult(
                document_name=pdf.name,
                output_file="",
                pii_count=0,
                status="failed",
                error=str(exc),
            )

        results.append(result)
        if on_progress:
            on_progress(result)

    return results
