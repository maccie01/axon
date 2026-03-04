"""Interactive Textual TUI for DocShield."""

from __future__ import annotations

import json
import logging
import platform
import subprocess
import sys
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from textual import work
from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import (
    Collapsible,
    Footer,
    Header,
    RichLog,
    Static,
)

from docshield.log import setup_logging

if TYPE_CHECKING:
    from docshield.config import PipelineConfig

logger = logging.getLogger("docshield.interactive")

_CLIPBOARD_CHAR_LIMIT = 80_000

_HELP_TEXT = """\
[bold]Workflow[/bold]

  1.  Place PDF files into [bold]input/[/bold].
  2.  Press [bold]1[/bold] to sanitize.
  3.  Press [bold]2[/bold] to see available prompts.
      Press a letter key ([bold]b / c / u / e[/bold]) to copy
      the prompt to your clipboard.  For larger documents the
      files are placed in [bold]output/llm_input/[/bold] to
      attach to your AI instead.
  4.  Save the AI response as a file in [bold]llm_responses/[/bold].
  5.  Press [bold]3[/bold] to restore all files at once.
  6.  Press [bold]x[/bold] to clean up generated files.

[bold]Prompt keys[/bold]

  [bold]b[/bold]  Base instructions  (placeholder rules only)
  [bold]c[/bold]  Compare documents
  [bold]u[/bold]  Summarize document
  [bold]e[/bold]  Extract requirements

[bold]Cleanup keys[/bold]  (after pressing x)

  [bold]o[/bold]  Clean output files
  [bold]m[/bold]  Clean mapping/vault files
  [bold]l[/bold]  Clean LLM responses
  [bold]a[/bold]  Clean all of the above

[bold]Custom terms[/bold]

  Copy [bold]data/custom_terms.example.txt[/bold] to
  [bold]data/custom_terms.txt[/bold] and add one term per line.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dir_files(path: Path, pred) -> list[Path]:
    if not path.exists():
        return []
    return sorted(f for f in path.iterdir() if f.is_file() and pred(f))


def _state(cfg: PipelineConfig) -> dict[str, list[Path]]:
    return {
        "pdfs":     _dir_files(cfg.input_dir, lambda f: f.suffix.lower() == ".pdf"),
        "clean":    _dir_files(cfg.output_dir, lambda f: f.name.startswith("CLEAN_")),
        "restored": _dir_files(cfg.output_dir, lambda f: f.name.startswith("RESTORED_")),
        "vaults":   _dir_files(cfg.mapping_dir, lambda f: f.name.startswith("VAULT_")),
        "llm":      _dir_files(cfg.llm_responses_dir, lambda f: not f.name.startswith(".")),
        "prompts":  _dir_files(Path("data/prompts"), lambda f: f.suffix in {".md", ".txt"}),
    }


def _file_summary(files: list[Path], label: str) -> str:
    n = len(files)
    if not n:
        return f"[dim]{label:<16}  --[/dim]"
    names = "  ".join(f.name for f in files[:3])
    extra = f"  [dim]+{n - 3} more[/dim]" if n > 3 else ""
    return (
        f"[bold]{label:<16}[/bold]  [green]{n}[/green]"
        f"  [dim]{names}{extra}[/dim]"
    )


def _human_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


def _copy_to_clipboard(text: str) -> bool:
    try:
        system = platform.system()
        if system == "Darwin":
            subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
        elif system == "Linux":
            subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=text.encode("utf-8"), check=True,
            )
        elif system == "Windows":
            subprocess.run(["clip"], input=text.encode("utf-8"), check=True)
        else:
            return False
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def _read_prompt(name: str) -> str | None:
    for ext in (".md", ".txt"):
        path = Path("data/prompts") / f"{name}{ext}"
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    return None


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

class DocShieldApp(App):
    TITLE = "DocShield"
    SUB_TITLE = "Privacy-first PDF anonymization"

    CSS = """
    Screen { background: $surface; }
    #main-scroll { height: 1fr; padding: 1 2; }
    #status-content { padding: 0 1; }
    #sanitize-log { height: auto; max-height: 20; }
    #prompts-log  { height: auto; max-height: 14; padding: 0 1; }
    #restore-log  { height: auto; max-height: 20; padding: 0 1; }
    #clean-log    { height: auto; max-height: 10; padding: 0 1; }
    .hint { padding: 0 1; color: $text-muted; }
    #help-body { padding: 0 1; }
    Collapsible { margin-bottom: 1; }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("1", "sanitize", "Sanitize", show=True),
        Binding("2", "prompts", "Prompts", show=True),
        Binding("3", "restore", "Restore", show=True),
        Binding("x", "clean", "Clean", show=True),
        Binding("b", "prompt_base", show=False),
        Binding("c", "prompt_compare", show=False),
        Binding("u", "prompt_summarize", show=False),
        Binding("e", "prompt_extract", show=False),
        Binding("o", "clean_output", show=False),
        Binding("m", "clean_mapping", show=False),
        Binding("l", "clean_llm", show=False),
        Binding("a", "clean_all", show=False),
        Binding("s", "refresh_status", "Refresh", show=True),
        Binding("h", "toggle_help", "Help", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    def __init__(self, cfg: PipelineConfig) -> None:
        super().__init__()
        self._cfg = cfg
        setup_logging(log_dir=cfg.log_dir, verbose=cfg.verbose)

    def get_system_commands(
        self, screen: object,
    ) -> Generator[SystemCommand, None, None]:
        for cmd in super().get_system_commands(screen):
            if "maximize" in cmd.title.lower():
                continue
            yield cmd

    # -- Layout (workflow order: status -> sanitize -> prompts -> restore) --

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="main-scroll"):
            with Collapsible(title="File Status", collapsed=False, id="sec-status"):
                yield Static(id="status-content")

            with Collapsible(title="Sanitize", collapsed=True, id="sec-sanitize"):
                yield Static(
                    "[dim]Press [bold]1[/bold] to sanitize PDFs.[/dim]",
                    classes="hint", id="sanitize-hint",
                )
                yield RichLog(id="sanitize-log", highlight=True, markup=True)

            with Collapsible(title="Prompts", collapsed=True, id="sec-prompts"):
                yield Static(
                    "[dim]Press [bold]2[/bold] to see available prompts.[/dim]",
                    classes="hint", id="prompts-hint",
                )
                yield RichLog(id="prompts-log", highlight=True, markup=True)

            with Collapsible(title="Restore", collapsed=True, id="sec-restore"):
                yield Static(
                    "[dim]Save AI responses to [bold]llm_responses/[/bold], "
                    "then press [bold]3[/bold].[/dim]",
                    classes="hint", id="restore-hint",
                )
                yield RichLog(id="restore-log", highlight=True, markup=True)

            with Collapsible(title="Clean Up", collapsed=True, id="sec-clean"):
                yield Static(
                    "[dim]Press [bold]x[/bold] to see cleanup options.[/dim]",
                    classes="hint", id="clean-hint",
                )
                yield RichLog(id="clean-log", highlight=True, markup=True)

            with Collapsible(title="Help", collapsed=True, id="sec-help"):
                yield Static(_HELP_TEXT, id="help-body", markup=True)
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_file_status()

    # -- Status --------------------------------------------------------

    def _refresh_file_status(self) -> None:
        st = _state(self._cfg)
        widget = self.query_one("#status-content", Static)
        widget.update("\n".join([
            _file_summary(st["pdfs"],      "input/"),
            _file_summary(st["clean"],     "output/clean"),
            _file_summary(st["restored"],  "output/restored"),
            _file_summary(st["vaults"],    "mapping/"),
            _file_summary(st["llm"],       "llm_responses/"),
            _file_summary(st["prompts"],   "data/prompts/"),
        ]))

    def action_refresh_status(self) -> None:
        self._refresh_file_status()
        self.notify("Refreshed")

    def action_toggle_help(self) -> None:
        sec = self.query_one("#sec-help", Collapsible)
        sec.collapsed = not sec.collapsed

    # -- Sanitize ------------------------------------------------------

    def action_sanitize(self) -> None:
        if not _state(self._cfg)["pdfs"]:
            self.notify("No PDFs in input/", severity="warning")
            return
        self.query_one("#sec-sanitize", Collapsible).collapsed = False
        self.query_one("#sanitize-hint", Static).update(
            "[bold]Sanitizing...[/bold]  [dim]initializing[/dim]"
        )
        self.query_one("#sanitize-log", RichLog).clear()
        self._run_sanitize()

    @work(thread=True)
    def _run_sanitize(self) -> None:
        log = self.query_one("#sanitize-log", RichLog)
        try:
            self._exec_worker(log)
        except Exception as exc:
            logger.exception("Sanitize failed")
            log.write(f"\n[bold red]Error:[/bold red] {exc}")
            self.call_from_thread(self._sanitize_error, str(exc))
            return
        self.call_from_thread(self._sanitize_done)

    def _exec_worker(self, log: RichLog) -> None:
        cfg = self._cfg
        cfg_json = json.dumps({
            "input_dir": str(cfg.input_dir),
            "output_dir": str(cfg.output_dir),
            "mapping_dir": str(cfg.mapping_dir),
            "log_dir": str(cfg.log_dir),
            "llm_responses_dir": str(cfg.llm_responses_dir),
            "model_id": cfg.model_id,
            "labels": cfg.labels,
            "ocr_languages": cfg.ocr_languages,
            "min_confidence": cfg.min_confidence,
            "custom_terms_file": (
                str(cfg.custom_terms_file) if cfg.custom_terms_file else None
            ),
            "verbose": cfg.verbose,
        })
        proc = subprocess.Popen(
            [sys.executable, "-m", "docshield.engine._worker", cfg_json],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1,
        )
        logger.info("Worker pid=%d", proc.pid)
        for raw in proc.stdout:
            raw = raw.strip()
            if not raw:
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                log.write(f"[dim]{raw}[/dim]")
                continue
            self._worker_msg(msg, log)

        proc.wait()
        err = proc.stderr.read().strip() if proc.stderr else ""
        if proc.returncode:
            raise RuntimeError(
                f"Worker exit {proc.returncode}" + (f": {err}" if err else "")
            )

    def _worker_msg(self, m: dict, log: RichLog) -> None:
        t = m.get("t")
        if t == "status":
            log.write(f"[dim]{m['msg']}[/dim]")
        elif t == "start":
            log.write(f"  [dim]---[/dim]  {m['name']}  [dim]extracting[/dim]")
        elif t == "ok":
            log.write(
                f"  [green]>>>[/green]  {m['name']}  "
                f"[dim]{m['pii']} flags  ({m['secs']}s)[/dim]"
            )
        elif t == "fail":
            log.write(f"  [red]x[/red]  {m['name']}  [red]{m['err']}[/red]")
        elif t == "done":
            log.write("")
            parts = [f"[bold green]{m['ok']} ok[/bold green]"]
            if m["failed"]:
                parts.append(f"[bold red]{m['failed']} failed[/bold red]")
            parts.append(
                f"[dim]{m['pii']} flags  ({m['secs']}s)[/dim]"
            )
            log.write("  ".join(parts))
            if m["ok"]:
                log.write("")
                log.write(
                    "[bold]Next:[/bold]  Press [bold]2[/bold] for prompts, "
                    "or press [bold]c[/bold] to copy the compare prompt."
                )
        elif t == "fatal":
            raise RuntimeError(m["err"])

    def _sanitize_done(self) -> None:
        self.query_one("#sanitize-hint", Static).update(
            "[green]Done.[/green]  [dim]Press [bold]2[/bold] "
            "for prompts, [bold]1[/bold] to re-run.[/dim]"
        )
        self._refresh_file_status()
        self.notify("Sanitization complete")

    def _sanitize_error(self, msg: str) -> None:
        self.query_one("#sanitize-hint", Static).update(
            f"[bold red]Failed.[/bold red] [dim]{msg}[/dim]"
        )
        self.notify(f"Failed: {msg}", severity="error")

    # -- Prompts -------------------------------------------------------

    def action_prompts(self) -> None:
        self.query_one("#sec-prompts", Collapsible).collapsed = False
        log = self.query_one("#prompts-log", RichLog)
        log.clear()

        clean = _state(self._cfg)["clean"]
        n = len(clean)
        sz = _human_size(sum(f.stat().st_size for f in clean)) if clean else "--"
        info = f"+ {n} doc(s), {sz}" if n else "[yellow]no docs yet[/yellow]"

        log.write(
            "  [bold]b[/bold]  Base instructions  "
            "[dim](placeholder rules only)[/dim]"
        )
        log.write(f"  [bold]c[/bold]  Compare documents  [dim]{info}[/dim]")
        log.write(f"  [bold]u[/bold]  Summarize document  [dim]{info}[/dim]")
        log.write(f"  [bold]e[/bold]  Extract requirements  [dim]{info}[/dim]")
        log.write("")

        over = n and sum(f.stat().st_size for f in clean) > _CLIPBOARD_CHAR_LIMIT
        if over:
            log.write(
                "[dim]Documents are large -- files will be prepared "
                "in [bold]output/llm_input/[/bold] for attachment.[/dim]"
            )
        else:
            log.write(
                "[dim]Prompt and documents are copied to clipboard "
                "together.[/dim]"
            )

        self.query_one("#prompts-hint", Static).update(
            "[dim]Press [bold]b[/bold], [bold]c[/bold], [bold]u[/bold], "
            "or [bold]e[/bold] to copy a prompt.[/dim]"
        )

    def action_prompt_base(self) -> None:
        text = _read_prompt("base_instructions")
        if not text:
            self.notify("base_instructions not found.", severity="error")
            return
        if _copy_to_clipboard(text):
            self._prompt_feedback("Base Instructions", clipboard_only=True)
        else:
            self.notify("Clipboard failed.", severity="error")

    def action_prompt_compare(self) -> None:
        self._copy_prompt_with_docs("compare_documents", "Compare Documents")

    def action_prompt_summarize(self) -> None:
        self._copy_prompt_with_docs("summarize_document", "Summarize Document")

    def action_prompt_extract(self) -> None:
        self._copy_prompt_with_docs(
            "extract_requirements", "Extract Requirements",
        )

    def _copy_prompt_with_docs(self, name: str, label: str) -> None:
        prompt = _read_prompt(name)
        if not prompt:
            self.notify(f"'{name}' prompt not found.", severity="error")
            return

        clean = sorted(self._cfg.output_dir.glob("CLEAN_*.md"))
        if not clean:
            if _copy_to_clipboard(prompt):
                self._prompt_feedback(label, clipboard_only=True)
            return

        total = sum(f.stat().st_size for f in clean) + len(prompt)

        if total <= _CLIPBOARD_CHAR_LIMIT:
            self._clipboard_approach(prompt, clean, label)
        else:
            self._file_approach(prompt, clean, label)

    def _clipboard_approach(
        self, prompt: str, files: list[Path], label: str,
    ) -> None:
        parts = [prompt, ""]
        for idx, fp in enumerate(files, 1):
            content = fp.read_text(encoding="utf-8").strip()
            parts.append("---")
            parts.append(f"\n## Document {idx}: {fp.stem}\n")
            parts.append(content)
        assembled = "\n".join(parts)

        if not _copy_to_clipboard(assembled):
            self.notify("Clipboard failed.", severity="error")
            return

        sz = _human_size(len(assembled.encode("utf-8")))
        self._prompt_feedback(
            label,
            extra=f"Prompt + {len(files)} doc(s) copied ({sz})",
        )
        logger.info("Clipboard: %s + %d docs (%s)", label, len(files), sz)

    def _file_approach(
        self, prompt: str, files: list[Path], label: str,
    ) -> None:
        input_dir = self._cfg.output_dir / "llm_input"
        input_dir.mkdir(exist_ok=True)
        for old in input_dir.iterdir():
            if old.is_file():
                old.unlink()

        prepared: list[Path] = []
        for idx, fp in enumerate(files, 1):
            dest_name = f"{idx}_{fp.name.removeprefix('CLEAN_')}"
            dest = input_dir / dest_name
            dest.write_text(fp.read_text(encoding="utf-8"), encoding="utf-8")
            prepared.append(dest)

        if not _copy_to_clipboard(prompt):
            self.notify("Clipboard failed.", severity="error")
            return

        sec = self.query_one("#sec-prompts", Collapsible)
        sec.collapsed = False
        log = self.query_one("#prompts-log", RichLog)
        log.clear()

        log.write(
            f"[green]>>>[/green]  [bold]{label}[/bold] prompt "
            f"copied to clipboard."
        )
        log.write(
            f"  [dim]{len(prepared)} document(s) prepared in "
            f"[bold]{input_dir}/[/bold][/dim]"
        )
        log.write("")
        for p in prepared:
            log.write(f"  [dim]-> {p.name}[/dim]")
        log.write("")
        log.write(
            "[bold]Steps:[/bold]\n"
            "  1. Paste the prompt into your AI\n"
            f"  2. Attach files from [bold]{input_dir}/[/bold]\n"
            "  3. Save AI response to [bold]llm_responses/[/bold]\n"
            "  4. Press [bold]3[/bold] to restore"
        )
        self.notify(f"Copied: {label} (files in llm_input/)")
        logger.info("File approach: %s + %d docs", label, len(prepared))

    def _prompt_feedback(
        self, label: str, *, clipboard_only: bool = False, extra: str = "",
    ) -> None:
        sec = self.query_one("#sec-prompts", Collapsible)
        sec.collapsed = False
        log = self.query_one("#prompts-log", RichLog)
        log.clear()

        log.write(
            f"[green]>>>[/green]  [bold]{label}[/bold] copied to clipboard."
        )
        if extra:
            log.write(f"  [dim]{extra}[/dim]")
        log.write("")
        if clipboard_only:
            log.write(
                "[dim]Paste into your AI together with the "
                "document content.[/dim]"
            )
        else:
            log.write(
                "[dim]Paste into your AI.  Save the response to "
                "[bold]llm_responses/[/bold], then press [bold]3[/bold].[/dim]"
            )
        self.notify(f"Copied: {label}")

    # -- Restore (automatic) -------------------------------------------

    def action_restore(self) -> None:
        from docshield.restore import (
            build_master_vault,
            collect_llm_files,
            restore_file,
        )

        cfg = self._cfg
        if not _state(cfg)["vaults"]:
            self.notify("No vault files -- run sanitize first.", severity="warning")
            return

        files = collect_llm_files(cfg.llm_responses_dir)
        if not files:
            self.notify(f"No files in {cfg.llm_responses_dir}/", severity="warning")
            return

        self.query_one("#sec-restore", Collapsible).collapsed = False
        log = self.query_one("#restore-log", RichLog)
        log.clear()
        self.query_one("#restore-hint", Static).update(
            f"[bold]Restoring {len(files)} file(s)...[/bold]"
        )

        vault = build_master_vault(cfg.mapping_dir)
        if not vault:
            self.notify("No vault mappings found.", severity="error")
            return

        results = []
        for fp in files:
            r = restore_file(fp, cfg.output_dir, vault, bold=True)
            results.append(r)
            log.write(
                f"  [green]>>>[/green]  {r.source}  ->  "
                f"[bold]{r.output}[/bold]  "
                f"[dim]({r.flags_restored} flags, "
                f"{_human_size(r.chars)})[/dim]"
            )

        log.write("")
        log.write(
            f"[bold green]{len(results)} file(s) restored[/bold green]  "
            f"[dim]({len(vault)} flags in vault)[/dim]"
        )

        if results:
            out_path = cfg.output_dir / results[0].output
            if out_path.exists():
                from rich.markup import escape

                content = out_path.read_text(encoding="utf-8")
                preview = content[:1000]
                log.write("")
                log.write("[dim]--- Preview ---[/dim]")
                log.write(escape(preview))
                if len(content) > 1000:
                    log.write("[dim]... (see full file)[/dim]")
                log.write("[dim]---[/dim]")

        self.query_one("#restore-hint", Static).update(
            f"[green]Restored {len(results)} file(s).[/green]  "
            "[dim]Check [bold]output/RESTORED_*[/bold][/dim]"
        )
        self._refresh_file_status()
        self.notify(f"Restored {len(results)} file(s)")
        logger.info("Restored %d file(s)", len(results))

    # -- Cleanup -----------------------------------------------------------

    _clean_active: bool = False

    def action_clean(self) -> None:
        sec = self.query_one("#sec-clean", Collapsible)
        sec.collapsed = False
        log = self.query_one("#clean-log", RichLog)
        log.clear()
        log.write("[bold]Choose what to clean:[/bold]")
        log.write("")
        log.write("  [bold]o[/bold]  output/ (CLEAN_*, RESTORED_*, llm_input/)")
        log.write("  [bold]m[/bold]  mapping/ (VAULT_*.json)")
        log.write("  [bold]l[/bold]  llm_responses/")
        log.write("  [bold]a[/bold]  all of the above")
        log.write("")
        log.write("[dim]Press a key or Escape to cancel.[/dim]")
        self._clean_active = True

    def _do_clean(self, targets: list[str]) -> None:
        cfg = self._cfg
        removed = 0

        if "output" in targets:
            for f in cfg.output_dir.iterdir():
                if f.is_file() and (
                    f.name.startswith("CLEAN_")
                    or f.name.startswith("RESTORED_")
                ):
                    f.unlink()
                    removed += 1
            llm_input = cfg.output_dir / "llm_input"
            if llm_input.is_dir():
                for f in llm_input.iterdir():
                    if f.is_file():
                        f.unlink()
                        removed += 1

        if "mapping" in targets:
            for f in cfg.mapping_dir.iterdir():
                if f.is_file() and f.name.startswith("VAULT_"):
                    f.unlink()
                    removed += 1

        if "llm" in targets:
            for f in cfg.llm_responses_dir.iterdir():
                if f.is_file() and not f.name.startswith("."):
                    f.unlink()
                    removed += 1

        log = self.query_one("#clean-log", RichLog)
        log.clear()
        cleaned = ", ".join(targets)
        log.write(f"[green]Cleaned {removed} file(s)[/green] from: {cleaned}")
        self.query_one("#clean-hint", Static).update(
            f"[green]Removed {removed} file(s).[/green]"
        )
        self._refresh_file_status()
        self.notify(f"Cleaned {removed} file(s)")
        logger.info("Cleanup: removed %d files from %s", removed, cleaned)

    def action_clean_output(self) -> None:
        if self._clean_active:
            self._clean_active = False
            self._do_clean(["output"])

    def action_clean_mapping(self) -> None:
        if self._clean_active:
            self._clean_active = False
            self._do_clean(["mapping"])

    def action_clean_llm(self) -> None:
        if self._clean_active:
            self._clean_active = False
            self._do_clean(["llm"])

    def action_clean_all(self) -> None:
        if self._clean_active:
            self._clean_active = False
            self._do_clean(["output", "mapping", "llm"])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(cfg: PipelineConfig) -> int:
    app = DocShieldApp(cfg)
    app.run()
    return 0
