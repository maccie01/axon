"""Dump Axon pipeline output for a snapshot directory to JSON.

Usage:
    uv run python tests/quality/dump_graph.py

Outputs draft JSON files to stdout sections that can be redirected
to the ground truth files after manual verification.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from axon.core.graph.graph import KnowledgeGraph
from axon.core.graph.model import NodeLabel, RelType
from axon.core.ingestion.pipeline import run_pipeline

SNAPSHOT_DIR = Path(__file__).resolve().parent / "data" / "docshield-snapshot"

SYMBOL_LABELS = {NodeLabel.FUNCTION, NodeLabel.CLASS, NodeLabel.METHOD}


def make_relative(file_path: str, root: Path) -> str:
    """Strip root prefix to get relative path."""
    try:
        return str(Path(file_path).relative_to(root))
    except ValueError:
        return file_path


def dump_symbols(graph: KnowledgeGraph, root: Path) -> list[dict]:
    symbols = []
    for node in graph.iter_nodes():
        if node.label not in SYMBOL_LABELS:
            continue
        symbols.append({
            "file": make_relative(node.file_path, root),
            "name": node.name,
            "kind": node.label.value,
            "line": node.start_line,
            "signature": node.signature,
            "is_dead": node.is_dead,
            "is_exported": node.is_exported,
            "class_name": node.class_name,
        })
    symbols.sort(key=lambda s: (s["file"], s["line"], s["name"]))
    return symbols


def dump_calls(graph: KnowledgeGraph, root: Path) -> list[dict]:
    calls = []
    for rel in graph.get_relationships_by_type(RelType.CALLS):
        source_node = graph.get_node(rel.source)
        target_node = graph.get_node(rel.target)
        if not source_node or not target_node:
            continue
        calls.append({
            "caller_file": make_relative(source_node.file_path, root),
            "caller_name": source_node.name,
            "callee_file": make_relative(target_node.file_path, root),
            "callee_name": target_node.name,
            "confidence": rel.properties.get("confidence", 1.0),
        })
    calls.sort(key=lambda c: (c["caller_file"], c["caller_name"], c["callee_name"]))
    return calls


def dump_imports(graph: KnowledgeGraph, root: Path) -> list[dict]:
    imports = []
    for rel in graph.get_relationships_by_type(RelType.IMPORTS):
        source_node = graph.get_node(rel.source)
        target_node = graph.get_node(rel.target)
        if not source_node or not target_node:
            continue
        imports.append({
            "source_file": make_relative(source_node.file_path, root),
            "source_name": source_node.name,
            "target_file": make_relative(target_node.file_path, root),
            "target_name": target_node.name,
        })
    imports.sort(key=lambda i: (i["source_file"], i["target_name"]))
    return imports


def dump_dead_code(graph: KnowledgeGraph, root: Path) -> list[dict]:
    dead = []
    for node in graph.iter_nodes():
        if node.label not in SYMBOL_LABELS:
            continue
        if node.is_dead:
            dead.append({
                "file": make_relative(node.file_path, root),
                "name": node.name,
                "kind": node.label.value,
            })
    dead.sort(key=lambda d: (d["file"], d["name"]))
    return dead


def dump_heritage(graph: KnowledgeGraph, root: Path) -> list[dict]:
    heritage = []
    for rel_type in (RelType.EXTENDS, RelType.IMPLEMENTS):
        for rel in graph.get_relationships_by_type(rel_type):
            source_node = graph.get_node(rel.source)
            target_node = graph.get_node(rel.target)
            if not source_node or not target_node:
                continue
            heritage.append({
                "child_file": make_relative(source_node.file_path, root),
                "child_name": source_node.name,
                "parent_name": target_node.name,
                "type": rel_type.value,
            })
    heritage.sort(key=lambda h: (h["child_file"], h["child_name"]))
    return heritage


def main():
    root = SNAPSHOT_DIR
    print(f"Indexing {root}...", file=sys.stderr)

    graph, result = run_pipeline(root, storage=None, embeddings=False)

    print(f"Pipeline complete: {result.files} files, {result.symbols} symbols, "
          f"{result.relationships} relationships", file=sys.stderr)
    print(f"Dead code flagged: {result.dead_code}", file=sys.stderr)

    output = {
        "meta": {
            "source": "docshield-snapshot",
            "files": result.files,
            "symbols": result.symbols,
            "relationships": result.relationships,
            "dead_code": result.dead_code,
        },
        "symbols": dump_symbols(graph, root),
        "calls": dump_calls(graph, root),
        "imports": dump_imports(graph, root),
        "dead_code": dump_dead_code(graph, root),
        "heritage": dump_heritage(graph, root),
    }

    json.dump(output, sys.stdout, indent=2)
    print(file=sys.stdout)  # trailing newline


if __name__ == "__main__":
    main()
