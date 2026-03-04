"""Subprocess worker for the PDF sanitization pipeline.

Running Docling/EasyOCR inside a Textual worker thread causes
multiprocessing deadlocks on Python 3.14+.  This module is designed to
be executed as a *separate process* via ``python -m docshield.engine._worker``
so that Docling operates in its own process without any Textual event-loop
interference.

Communication protocol (stdout, one JSON object per line):
    {"t":"status", "msg":"..."}       -- progress messages for the TUI log
    {"t":"start",  "name":"..."}      -- per-document start
    {"t":"ok",     "name":"...", "out":"...", "pii":N, "secs":N}
    {"t":"fail",   "name":"...", "err":"..."}
    {"t":"done",   "ok":N, "failed":N, "pii":N, "secs":N}
    {"t":"fatal",  "err":"..."}       -- unrecoverable error
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path


def _emit(**kwargs: object) -> None:
    sys.stdout.write(json.dumps(kwargs, default=str) + "\n")
    sys.stdout.flush()


def _run(cfg_json: dict) -> None:
    from docshield.config import PipelineConfig
    from docshield.engine import DocumentExtractor, IntelligentSanitizer
    from docshield.engine.custom_terms import load_custom_terms
    from docshield.pipeline import collect_pdfs, ensure_directories, process_documents

    cfg = PipelineConfig(
        input_dir=Path(cfg_json["input_dir"]),
        output_dir=Path(cfg_json["output_dir"]),
        mapping_dir=Path(cfg_json["mapping_dir"]),
        log_dir=Path(cfg_json["log_dir"]),
        llm_responses_dir=Path(cfg_json.get("llm_responses_dir", "llm_responses")),
        model_id=cfg_json["model_id"],
        labels=cfg_json["labels"],
        ocr_languages=cfg_json["ocr_languages"],
        min_confidence=cfg_json["min_confidence"],
        custom_terms_file=(
            Path(cfg_json["custom_terms_file"])
            if cfg_json.get("custom_terms_file")
            else None
        ),
        verbose=cfg_json.get("verbose", False),
    )

    t0 = time.monotonic()

    _emit(t="status", msg="Initializing Docling extractor...")
    extractor = DocumentExtractor(ocr_languages=cfg.ocr_languages)

    _emit(t="status", msg="Loading GLiNER model...")
    custom_terms = load_custom_terms(cfg.custom_terms_file)
    sanitizer = IntelligentSanitizer(
        labels=cfg.labels,
        model_id=cfg.model_id,
        min_confidence=cfg.min_confidence,
        custom_terms=custom_terms,
    )
    model_elapsed = time.monotonic() - t0
    _emit(t="status", msg=f"Engine ready ({model_elapsed:.1f}s).")

    ensure_directories([cfg.output_dir, cfg.mapping_dir, cfg.log_dir, cfg.llm_responses_dir])
    pdfs = collect_pdfs(cfg.input_dir)
    _emit(t="status", msg=f"Processing {len(pdfs)} PDF(s)...")

    ok_count = 0
    fail_count = 0
    total_pii = 0

    doc_start = time.monotonic()

    def on_start(name: str) -> None:
        nonlocal doc_start
        doc_start = time.monotonic()
        _emit(t="start", name=name)

    def on_progress(result) -> None:
        nonlocal ok_count, fail_count, total_pii
        doc_elapsed = time.monotonic() - doc_start
        if result.succeeded:
            ok_count += 1
            total_pii += result.pii_count
            _emit(
                t="ok",
                name=result.document_name,
                out=result.output_file,
                pii=result.pii_count,
                secs=round(doc_elapsed, 1),
            )
        else:
            fail_count += 1
            _emit(t="fail", name=result.document_name, err=result.error or "")

    process_documents(
        cfg.input_dir,
        cfg.output_dir,
        cfg.mapping_dir,
        extractor,
        sanitizer,
        on_progress=on_progress,
        on_start=on_start,
    )

    total_elapsed = time.monotonic() - t0
    _emit(
        t="done",
        ok=ok_count,
        failed=fail_count,
        pii=total_pii,
        secs=round(total_elapsed, 1),
    )


def main() -> None:
    try:
        cfg_json = json.loads(sys.argv[1])
        _run(cfg_json)
    except Exception as exc:  # noqa: BLE001
        _emit(t="fatal", err=str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
