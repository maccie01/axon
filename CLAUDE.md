# Axon -- Graph-Powered Code Intelligence Engine

Fork of [harshkedia177/axon](https://github.com/harshkedia177/axon) maintained at [maccie01/axon](https://github.com/maccie01/axon).

## Purpose

We use Axon as a **local MCP tool for Claude Code** to provide structural code intelligence across all our projects. It indexes codebases into a knowledge graph (KuzuDB) and exposes it via MCP tools so AI agents can answer architectural questions: blast radius, dead code, call chains, change coupling, execution flows.

Runs 100% locally. No cloud deps. Bound to 127.0.0.1 only.

## Current State: Alpha (v0.2.2) -- Not Production-Ready

The core pipeline and parsers are solid. The operational layer (watch mode, error handling, input validation) needs hardening before daily use. See issues below.

## What Works Well

- **11-phase pipeline**: Clean phase isolation, thin orchestrator (~160 LOC)
- **Tree-sitter parsers**: Python + TypeScript/JS. Handle edge cases well (decorators, CJS, overloads, receivers)
- **Dead code detection**: Multi-pass with override, Protocol conformance, and stub awareness. Framework-aware decorator exemptions
- **RRF hybrid search**: BM25 + vector + fuzzy with Reciprocal Rank Fusion
- **Change coupling**: Git history analysis with configurable window and commit-size guard
- **StorageBackend Protocol**: Clean port/adapter pattern. KuzuDB + optional Neo4j

## Issues Tracker

All issues are on the fork: https://github.com/maccie01/axon/issues

### P0 -- Fix Before Using

#### #1: Cypher Injection in detect_changes + FTS/fuzzy queries
- `tools.py:264-268` -- file_path from git diff interpolated into Cypher with only quote-stripping
- `kuzu_backend.py:316-323, 377-382` -- FTS/fuzzy queries use `_escape()` which misses null bytes, newlines
- The codebase already uses parameterized queries correctly in 10+ other methods -- these were missed
- **Fix**: Add `execute_parameterized()` to KuzuBackend, replace all string interpolation
- **Impact**: A prompt-injected agent feeding crafted diffs can corrupt the local knowledge graph

#### #2: Watch Mode Re-Runs Full Pipeline Every 30s
- `watcher.py:75-84` calls `run_pipeline(full=True)` which: re-walks ALL files, re-parses ALL files, DETACH DELETEs all nodes, bulk-loads everything from scratch
- On a 10k+ file codebase: 30-60s blocking. MCP queries hang during this window
- **Fix options**: (A) Incremental global phases on changed subgraph, (B) dirty-file-only refresh, (C) background thread without MCP lock
- **Acceptance**: Watch mode on 5k-file repo must not block MCP queries >2s

### P1 -- Reliability Before Production Use

#### #3: Call Resolution Wrong on Common Function Names
- `calls.py:164-178` -- `_pick_closest` uses "shortest file path" as tiebreaker
- Vendored code at `a/b.py` always wins over project code at `src/my_app/auth/validators.py`
- Common names (`get`, `validate`, `process`, `handle`) silently resolve to wrong targets
- These `confidence=0.5` edges are not filtered by consumers
- **Fix**: Replace with shared-path-prefix scoring + test-file penalty. Filter low-confidence edges from `handle_impact`

#### #4: reindex_files Skips Global Phases -- Dead Code Data Goes Stale
- `pipeline.py:163-204` runs only Phases 2-7. Phases 8-11 (communities, processes, dead code, coupling) skipped
- Between file change and next 30s global refresh, `axon_dead_code` returns stale data
- `PipelineResult.incremental` is never set to `True` -- dead field
- **Fix**: Run incremental dead code on changed symbols + their callers after reindex

#### #5: Git Ref Option Injection in diff_branches
- `diff.py:158-168` -- user-supplied ref passed directly to `git worktree add` without validation
- A ref starting with `-` (e.g. `--detach`) is interpreted as a git option
- **Fix**: Validate refs with `^[a-zA-Z0-9/_\-\.]+$`, reject `-` prefix, use `--` separator, add timeouts

#### #6: assert Guards Stripped Under python -O
- 15+ public methods in `kuzu_backend.py` use `assert self._conn is not None`
- `assert` is removed under `-O` flag, turning guards into silent `AttributeError`
- Combined with `except Exception: pass` everywhere, failures become invisible
- **Fix**: Add `_require_connection()` helper that raises `RuntimeError`

#### #7: bulk_load Silently Swallows Failures on Data-Mutating Operations
- `kuzu_backend.py:525-544` -- DETACH DELETE wrapped in `except Exception: pass`
- If cleanup fails, stale nodes persist + COPY FROM creates duplicates
- `_insert_node`, `_insert_relationship` failures logged at DEBUG level only
- **Fix**: Log writes at WARNING, count failures, raise if threshold exceeded

### P2 -- Make It More Powerful

#### #8: Add Go and Rust Parser Support
- Currently: Python, TypeScript, JavaScript only
- Tree-sitter grammars exist for Go and Rust
- Add as optional deps: `pip install axon[go]`, `pip install axon[rust]`
- Follow existing `python_lang.py` / `typescript.py` pattern

#### #9: Make fastembed and leidenalg Optional Dependencies
- `fastembed` (~200MB ONNX) only needed for vector search
- `leidenalg` + `igraph` (~50MB C extensions) only needed for community detection
- Move to `[project.optional-dependencies]` groups
- Skip phases gracefully if deps missing

#### #10: File Size Limits + Pipeline Error Boundary
- No max file size in `walker.py` -- 50MB generated bundles crash pipeline
- No try/except around individual phases in `run_pipeline()` -- one bad file kills watcher
- **Fix**: 1MB file size limit, per-phase error isolation, per-file parse isolation

#### #11: Wire Embeddings into Watch Mode
- `watcher.py` docstring describes embedding refresh tier but it is not implemented
- Vector search results go stale after file changes until manual `axon analyze --embed`
- **Fix**: Track changed symbols, re-embed delta every 60s

#### #12: Better Community Labels
- `community.py:generate_label()` produces "Src", "Lib", "Src+Lib" for most repos
- Useless for the MCP agent consuming `axon_context`
- **Fix**: Use 2-level directory prefixes or dominant class/module names

### P3 -- Hardening

#### #13: Cap depth/limit Parameters in MCP Tools
- `axon_impact` depth has no max -- agent can pass depth=999999
- `axon_query` limit has no max
- `execute_raw` has no query length or result row limit
- **Fix**: Schema-level bounds + handler-level clamps

## Architecture Overview

```
src/axon/
  cli/main.py              # CLI entrypoint (typer)
  config/
    ignore.py              # Gitignore handling (pathspec)
    languages.py           # Supported language registry
  core/
    graph/
      model.py             # GraphNode, GraphRelationship, NodeLabel, RelType
      graph.py             # In-memory KnowledgeGraph (4 secondary indexes)
    ingestion/
      pipeline.py          # 11-phase orchestrator
      walker.py            # File discovery + parallel read
      structure.py         # Phase 2: File/Folder nodes
      parser_phase.py      # Phase 3: Symbol extraction via tree-sitter
      imports.py           # Phase 4: Import resolution
      calls.py             # Phase 5: Call tracing + resolution
      heritage.py          # Phase 6: EXTENDS/IMPLEMENTS edges
      types.py             # Phase 7: USES_TYPE edges
      community.py         # Phase 8: Leiden community detection
      processes.py         # Phase 9: Execution flow detection
      dead_code.py         # Phase 10: Multi-pass dead code analysis
      coupling.py          # Phase 11: Git history change coupling
      watcher.py           # Watch mode (watchfiles)
      symbol_lookup.py     # Index builders for call resolution
    parsers/
      base.py              # ParseResult, SymbolInfo, CallInfo, ImportInfo
      python_lang.py       # Python parser (tree-sitter)
      typescript.py        # TS/JS parser (tree-sitter)
    search/
      hybrid.py            # RRF hybrid search (BM25 + vector + fuzzy)
    storage/
      base.py              # StorageBackend Protocol
      kuzu_backend.py      # KuzuDB implementation (843 LOC)
    diff.py                # Branch comparison via parallel worktrees
    embeddings/
      embedder.py          # fastembed ONNX embedding pipeline
      text.py              # Text preparation for embedding
  mcp/
    server.py              # MCP server (stdio)
    tools.py               # MCP tool handlers
    resources.py           # MCP resource handlers
```

## Key Design Patterns

- **In-memory intermediate graph**: Pipeline builds `KnowledgeGraph` (pure Python), then bulk-loads into KuzuDB. Keeps parsing fast and testable without a live DB
- **Phase-numbered pipeline**: Each phase is a standalone module. Adding/swapping phases is trivial
- **StorageBackend Protocol**: `@runtime_checkable` Protocol. KuzuDB is the default, Neo4j is optional
- **Single REL TABLE GROUP**: All relationship types share one `CodeRelation` table group with a `rel_type` discriminator. KuzuDB-specific pattern -- not portable to Neo4j without translation
- **Node IDs**: `{label}:{file_path}:{symbol_name}` -- fragile if paths contain colons

## Development

```bash
cd ~/tools/axon
uv sync                    # Install deps
uv run axon analyze .      # Index a repo
uv run axon serve          # Start MCP server
uv run axon watch .        # Watch mode
uv run pytest              # Run tests
```

## Conventions

- Commits: conventional (`feat:`, `fix:`, `refactor:`)
- Author: Jan Schubert (never as claude, no co-author)
- No emojis in code or docs
- German Umlaute where applicable
