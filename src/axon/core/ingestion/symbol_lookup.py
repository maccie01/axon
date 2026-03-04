"""Shared symbol lookup utilities for ingestion phases.

Provides line-based containment lookups using a pre-built per-file
interval index.
"""

from __future__ import annotations

from collections import defaultdict

from axon.core.graph.graph import KnowledgeGraph
from axon.core.graph.model import GraphNode, NodeLabel


def build_name_index(
    graph: KnowledgeGraph,
    labels: tuple[NodeLabel, ...],
) -> dict[str, list[str]]:
    """Build a mapping from symbol names to their node IDs.

    Iterates over all nodes matching the given *labels* and groups
    them by name.  Multiple symbols can share the same name across
    different files, so each entry maps to a list of node IDs.

    This is the shared implementation used by calls, heritage, and
    type analysis phases.
    """
    index: dict[str, list[str]] = {}
    for label in labels:
        for node in graph.get_nodes_by_label(label):
            index.setdefault(node.name, []).append(node.id)
    return index


class FileSymbolIndex:
    """Pre-built per-file interval index for containment lookups.

    Stores ``(start_line, end_line, span, node_id)`` tuples sorted by
    ``start_line``.  Lookups scan all entries for a file to find the
    narrowest containing span (typically <200 symbols per file).
    """

    __slots__ = ("_entries",)

    def __init__(
        self,
        entries: dict[str, list[tuple[int, int, int, str]]],
    ) -> None:
        self._entries = entries

    def get_entries(self, file_path: str) -> list[tuple[int, int, int, str]] | None:
        return self._entries.get(file_path)

def build_file_symbol_index(
    graph: KnowledgeGraph,
    labels: tuple[NodeLabel, ...],
) -> FileSymbolIndex:
    """Build a per-file sorted interval index for containment lookups.

    For each file, symbols are stored as ``(start_line, end_line, span, node_id)``
    tuples sorted by ``start_line``.

    Args:
        graph: The knowledge graph containing parsed symbol nodes.
        labels: Which node labels to include in the index.

    Returns:
        A :class:`FileSymbolIndex` with entries per file.
    """
    entries: dict[str, list[tuple[int, int, int, str]]] = defaultdict(list)

    for label in labels:
        for node in graph.get_nodes_by_label(label):
            if node.file_path and node.start_line > 0:
                span = node.end_line - node.start_line
                entries[node.file_path].append(
                    (node.start_line, node.end_line, span, node.id)
                )

    for file_entries in entries.values():
        file_entries.sort(key=lambda t: t[0])

    return FileSymbolIndex(entries)

def find_containing_symbol(
    line: int,
    file_path: str,
    file_symbol_index: FileSymbolIndex,
) -> str | None:
    """Find the most specific symbol whose line range contains *line*.

    Args:
        line: The source line number to look up.
        file_path: Path to the file containing the line.
        file_symbol_index: Pre-built index from :func:`build_file_symbol_index`.

    Returns:
        The node ID of the most specific (smallest span) containing symbol,
        or ``None`` if no symbol contains the given line.
    """
    entries = file_symbol_index.get_entries(file_path)
    if not entries:
        return None

    best_id: str | None = None
    best_span = float("inf")

    # Scan all entries for the file to find the narrowest containing span.
    # Files typically have <200 symbols so a full scan is fast and correct
    # (the previous ±10 window could miss deeply nested symbols).
    for start, end, span, nid in entries:
        if start <= line <= end and span < best_span:
            best_span = span
            best_id = nid

    return best_id
