"""Command-line interface for DocShield."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from docshield.config import (
    DEFAULT_CUSTOM_TERMS_FILE,
    DEFAULT_LABELS,
    DEFAULT_MIN_CONFIDENCE,
    DEFAULT_MODEL_ID,
    DEFAULT_OCR_LANGUAGES,
    PipelineConfig,
)
from docshield.log import setup_logging

# ---------------------------------------------------------------------------
# Argument helpers
# ---------------------------------------------------------------------------

def _add_sanitize_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", default="input", metavar="DIR",
                        help="Input PDF directory (default: input)")
    parser.add_argument("--output", default="output", metavar="DIR",
                        help="Output Markdown directory (default: output)")
    parser.add_argument("--mapping", default="mapping", metavar="DIR",
                        help="Vault mapping directory (default: mapping)")
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID, metavar="ID",
                        help=f"GLiNER model id (default: {DEFAULT_MODEL_ID})")
    parser.add_argument("--labels", default=",".join(DEFAULT_LABELS), metavar="LIST",
                        help="Comma-separated semantic labels for detection")
    parser.add_argument("--ocr-languages",
                        default=",".join(DEFAULT_OCR_LANGUAGES), metavar="LIST",
                        help="Comma-separated OCR languages (default: de,en)")
    parser.add_argument("--min-confidence", type=float,
                        default=DEFAULT_MIN_CONFIDENCE, metavar="N",
                        help=f"GLiNER confidence threshold (default: {DEFAULT_MIN_CONFIDENCE})")
    parser.add_argument("--custom-terms", default=DEFAULT_CUSTOM_TERMS_FILE,
                        metavar="FILE",
                        help="Custom terms file for forced masking "
                             f"(default: {DEFAULT_CUSTOM_TERMS_FILE})")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable debug logging")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON (for agent/script use)")


# ---------------------------------------------------------------------------
# Parser construction
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="docshield",
        description="DocShield: privacy-first PDF anonymization pipeline.",
        epilog=(
            "Examples:\n"
            "  docshield                  # anonymize all PDFs in input/\n"
            "  docshield sanitize -v      # same, with debug output\n"
            "  docshield restore          # restore files in llm_responses/\n"
            "  docshield status           # show what's in each directory\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.set_defaults(command=None)
    _add_sanitize_args(parser)  # backward compat: `docshield --input foo`

    subs = parser.add_subparsers(dest="command", metavar="COMMAND")

    # -- sanitize -------------------------------------------------------------
    san = subs.add_parser("sanitize", help="Anonymize PDFs in input/ (default command)")
    _add_sanitize_args(san)

    # -- restore --------------------------------------------------------------
    res = subs.add_parser("restore", help="Restore PII flags in LLM output")
    res.add_argument("--mapping", default="mapping", metavar="DIR",
                     help="Vault mapping directory (default: mapping)")
    res.add_argument("--input", default="llm_responses", metavar="PATH",
                     help="LLM response file or directory (default: llm_responses)")
    res.add_argument("--output", default="output", metavar="DIR",
                     help="Output directory for restored files (default: output)")
    res.add_argument("--no-bold", action="store_true",
                     help="Do not bold restored values")
    res.add_argument("--verbose", "-v", action="store_true",
                     help="Enable debug logging")
    res.add_argument("--json", action="store_true",
                     help="Output results as JSON (for agent/script use)")

    # -- status ---------------------------------------------------------------
    stat = subs.add_parser("status", help="Show pipeline directory status at a glance")
    stat.add_argument("--input", default="input", metavar="DIR")
    stat.add_argument("--output", default="output", metavar="DIR")
    stat.add_argument("--mapping", default="mapping", metavar="DIR")
    stat.add_argument("--json", action="store_true",
                      help="Output results as JSON (for agent/script use)")

    return parser


# Kept for backward compatibility with tests
def _build_main_parser() -> argparse.ArgumentParser:
    return _build_parser()


def _build_restore_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="docshield-restore",
        description="Restore masked PII flags in LLM output using vault mappings.",
    )
    parser.add_argument("--mapping", default="mapping",
                        help="Vault mapping directory (default: mapping)")
    parser.add_argument("--input", default="llm_responses",
                        help="LLM response file or directory (default: llm_responses)")
    parser.add_argument("--output", default="output",
                        help="Output directory for restored files (default: output)")
    parser.add_argument("--no-bold", action="store_true",
                        help="Do not bold restored values")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable debug logging")
    return parser


# ---------------------------------------------------------------------------
# Rich helpers
# ---------------------------------------------------------------------------

def _get_console():  # type: ignore[return]
    try:
        from rich.console import Console
        return Console()
    except ImportError:
        return None


def _info(console, msg: str) -> None:
    if console:
        console.print(msg)
    else:
        # Strip rich markup for plain output
        import re
        print(re.sub(r"\[/?[^\]]+\]", "", msg))


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------

def _cmd_sanitize(args: argparse.Namespace) -> int:
    use_json = getattr(args, "json", False)
    ct = getattr(args, "custom_terms", DEFAULT_CUSTOM_TERMS_FILE)
    cfg = PipelineConfig(
        input_dir=Path(args.input),
        output_dir=Path(args.output),
        mapping_dir=Path(args.mapping),
        model_id=args.model_id,
        labels=[lb.strip() for lb in args.labels.split(",") if lb.strip()],
        ocr_languages=[
            lg.strip() for lg in args.ocr_languages.split(",") if lg.strip()
        ],
        min_confidence=args.min_confidence,
        custom_terms_file=Path(ct) if ct else None,
        verbose=args.verbose,
    )
    setup_logging(log_dir=cfg.log_dir, verbose=cfg.verbose)

    console = None if use_json else _get_console()

    from docshield.engine import DocumentExtractor, IntelligentSanitizer
    from docshield.engine.custom_terms import load_custom_terms
    from docshield.pipeline import collect_pdfs, ensure_directories, process_documents

    custom_terms = load_custom_terms(cfg.custom_terms_file)

    ensure_directories([
        cfg.input_dir, cfg.output_dir, cfg.mapping_dir,
        cfg.log_dir, cfg.llm_responses_dir,
    ])

    pdfs = collect_pdfs(cfg.input_dir)
    if not pdfs:
        if use_json:
            print(json.dumps({"command": "sanitize", "ok": 0, "failed": 0,
                               "total_pii": 0, "documents": [],
                               "error": f"No PDFs found in {cfg.input_dir}/"}))
        else:
            _info(console,
                  f"[yellow]No PDFs found in {cfg.input_dir}/[/yellow]  "
                  "Drop PDFs there and run again.")
        return 0

    if use_json:
        print(f"Loading model and processing {len(pdfs)} PDF(s)…", file=sys.stderr)
        extractor = DocumentExtractor(ocr_languages=cfg.ocr_languages)
        sanitizer = IntelligentSanitizer(
            labels=cfg.labels, model_id=cfg.model_id,
            min_confidence=cfg.min_confidence,
            custom_terms=custom_terms,
        )
    elif console:
        with console.status("[bold]Loading GLiNER model…[/bold]", spinner="dots"):
            t0 = time.monotonic()
            extractor = DocumentExtractor(ocr_languages=cfg.ocr_languages)
            sanitizer = IntelligentSanitizer(
                labels=cfg.labels, model_id=cfg.model_id,
                min_confidence=cfg.min_confidence,
                custom_terms=custom_terms,
            )
        console.print(f"[dim]Model ready  ({time.monotonic() - t0:.1f}s)[/dim]\n")
    else:
        print("Loading GLiNER model…")
        extractor = DocumentExtractor(ocr_languages=cfg.ocr_languages)
        sanitizer = IntelligentSanitizer(
            labels=cfg.labels, model_id=cfg.model_id,
            min_confidence=cfg.min_confidence,
            custom_terms=custom_terms,
        )

    if not use_json:
        _info(console,
              f"Processing [bold]{len(pdfs)}[/bold] PDF(s) "
              f"from [bold]{cfg.input_dir}/[/bold]\n")

    def on_progress(result: object) -> None:
        from docshield.models import RunResult
        assert isinstance(result, RunResult)
        if use_json:
            return  # collect silently; JSON emitted at end
        name = result.document_name
        if result.succeeded:
            _info(console,
                  f"  [green]✓[/green]  {name:<45} "
                  f"[dim]{result.pii_count} PII flags[/dim]")
        else:
            _info(console,
                  f"  [red]✗[/red]  {name:<45} [red]{result.error}[/red]")

    results = process_documents(
        cfg.input_dir, cfg.output_dir, cfg.mapping_dir,
        extractor, sanitizer,
        on_progress=on_progress,
    )

    total_pii = sum(r.pii_count for r in results)
    ok = sum(1 for r in results if r.succeeded)
    failed = len(results) - ok

    if use_json:
        print(json.dumps({
            "command": "sanitize",
            "ok": ok,
            "failed": failed,
            "total_pii": total_pii,
            "documents": [
                {
                    "name": r.document_name,
                    "succeeded": r.succeeded,
                    "pii_count": r.pii_count,
                    "output_file": r.output_file,
                    "error": r.error,
                }
                for r in results
            ],
        }))
    else:
        summary = f"\n  [bold green]{ok} succeeded[/bold green]"
        if failed:
            summary += f"  [bold red]{failed} failed[/bold red]"
        summary += f"  [dim]·  {total_pii} PII flags masked[/dim]"
        _info(console, summary)

    return 1 if failed else 0


def _cmd_restore(args: argparse.Namespace) -> int:
    use_json = getattr(args, "json", False)
    setup_logging(verbose=getattr(args, "verbose", False))
    console = None if use_json else _get_console()

    from docshield.restore import run_restorer

    mapping_dir = Path(args.mapping)
    input_path = Path(args.input)
    output_dir = Path(getattr(args, "output", "output"))
    bold = not getattr(args, "no_bold", False)

    if not input_path.exists():
        msg = f"{input_path} not found"
        if use_json:
            print(json.dumps({"command": "restore", "error": msg}))
        else:
            _info(console, f"[yellow]{msg}[/yellow]")
        return 1

    rc = run_restorer(
        mapping_dir=mapping_dir,
        input_path=input_path,
        output_dir=output_dir,
        bold=bold,
    )

    if not use_json and rc == 0:
        _info(console, "[green]Restore complete.[/green]")
    return rc


def _cmd_status(args: argparse.Namespace) -> int:
    use_json = getattr(args, "json", False)
    console = None if use_json else _get_console()

    input_dir = Path(args.input)
    output_dir = Path(args.output)
    mapping_dir = Path(args.mapping)

    dirs = [
        ("input",   input_dir,   lambda p: p.suffix.lower() == ".pdf"),
        ("output",  output_dir,  lambda p: p.name.startswith("CLEAN_")),
        ("mapping", mapping_dir, lambda p: p.name.startswith("VAULT_")),
    ]

    if use_json:
        result: dict[str, object] = {"command": "status"}
        for key, path, filt in dirs:
            if not path.exists():
                result[key] = {"exists": False, "count": 0, "files": []}
            else:
                files = sorted(f.name for f in path.iterdir() if f.is_file() and filt(f))
                result[key] = {"exists": True, "count": len(files), "files": files}
        print(json.dumps(result))
    elif console:
        from rich.table import Table
        table = Table(title="DocShield Status", show_header=True, header_style="bold")
        table.add_column("Directory", style="bold")
        table.add_column("Files", justify="right")
        table.add_column("Contents")
        for key, path, filt in dirs:
            label = f"{key}/"
            if not path.exists():
                table.add_row(label, "—", "[dim]directory not found[/dim]")
                continue
            files = sorted(f for f in path.iterdir() if f.is_file() and filt(f))
            preview = ", ".join(f.name for f in files[:3])
            if len(files) > 3:
                preview += f"  [dim]+{len(files) - 3} more[/dim]"
            count_str = f"[green]{len(files)}[/green]" if files else "[dim]0[/dim]"
            table.add_row(label, count_str, preview or "[dim]empty[/dim]")
        console.print(table)
    else:
        for key, path, filt in dirs:
            if not path.exists():
                print(f"{key + '/':12s}  (not found)")
                continue
            files = sorted(f for f in path.iterdir() if f.is_file() and filt(f))
            print(f"{key + '/':12s}  {len(files)} file(s)")

    return 0


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """Entry point: docshield [sanitize|restore|status]"""
    args = _build_parser().parse_args(argv)

    if args.command is None:
        # No subcommand → interactive guided mode
        from docshield.interactive import run
        ct = getattr(args, "custom_terms", DEFAULT_CUSTOM_TERMS_FILE)
        cfg = PipelineConfig(
            input_dir=Path(args.input),
            output_dir=Path(args.output),
            mapping_dir=Path(args.mapping),
            model_id=args.model_id,
            labels=[lb.strip() for lb in args.labels.split(",") if lb.strip()],
            ocr_languages=[
                lg.strip() for lg in args.ocr_languages.split(",") if lg.strip()
            ],
            min_confidence=args.min_confidence,
            custom_terms_file=Path(ct) if ct else None,
            verbose=args.verbose,
        )
        setup_logging(log_dir=cfg.log_dir, verbose=cfg.verbose)
        return run(cfg)

    if args.command == "restore":
        return _cmd_restore(args)
    if args.command == "status":
        return _cmd_status(args)
    return _cmd_sanitize(args)


def restore(argv: list[str] | None = None) -> int:
    """Standalone entry point for docshield-restore (backward compat)."""
    args = _build_restore_parser().parse_args(argv)
    return _cmd_restore(args)
