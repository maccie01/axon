"""Golden codebase accuracy tests.

Measures precision and recall for symbol extraction and call edge detection
against manually verified ground truth in expected/symbols.yaml and
expected/calls.yaml.

Reports a score card at the end of each run.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from axon.core.storage.kuzu_backend import KuzuBackend

from .conftest import (
    call_edge_exists,
    load_expected,
    parse_edge_ref,
    symbol_exists,
)


# ---------------------------------------------------------------------------
# Score tracking
# ---------------------------------------------------------------------------


@dataclass
class PhaseScore:
    phase: str
    true_positives: int = 0
    false_negatives: int = 0  # expected but missing
    false_positives: int = 0  # present but should not be
    errors: list[str] = field(default_factory=list)

    @property
    def precision(self) -> float:
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    def status(self, min_precision: float, min_recall: float) -> str:
        if self.precision >= min_precision and self.recall >= min_recall:
            return "PASS"
        if self.precision >= min_precision * 0.9 and self.recall >= min_recall * 0.9:
            return "WARN"
        return "FAIL"


def _print_score_card(scores: list[PhaseScore]) -> None:
    print("\n\nAxon Quality Report (golden-codebase)")
    print("=" * 65)
    print(f"{'Phase':<20} {'Precision':>10} {'Recall':>8} {'F1':>8}  Status")
    print("-" * 65)
    for s in scores:
        status = s.status(0.85, 0.80)
        print(
            f"{s.phase:<20} {s.precision:>9.1%} {s.recall:>7.1%} {s.f1:>7.1%}  {status}"
        )
    print("=" * 65)
    for s in scores:
        if s.errors:
            print(f"\n[{s.phase}] issues:")
            for e in s.errors[:10]:
                print(f"  {e}")
            if len(s.errors) > 10:
                print(f"  ... and {len(s.errors) - 10} more")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSymbolExtraction:
    """Every declared symbol must exist in the graph after indexing."""

    def test_symbols_recall(self, golden_storage: KuzuBackend) -> None:
        """All expected symbols are found (recall)."""
        data = load_expected("symbols.yaml")
        score = PhaseScore("Symbols")
        min_recall = data.get("metrics", {}).get("minimum_recall", 0.90)

        for sym in data["symbols"]:
            file_path = sym["file"]
            # Parse symbol name: for methods like 'AuthService.authenticate'
            # the name stored in graph is the full qualified name
            name = sym["name"]
            if symbol_exists(golden_storage, file_path, name):
                score.true_positives += 1
            else:
                score.false_negatives += 1
                score.errors.append(f"MISSING: {file_path}::{name}")

        _print_score_card([score])

        assert score.recall >= min_recall, (
            f"Symbol recall {score.recall:.1%} below minimum {min_recall:.1%}\n"
            f"Missing: {[e for e in score.errors if e.startswith('MISSING')][:5]}"
        )

    def test_symbols_no_critical_gaps(self, golden_storage: KuzuBackend) -> None:
        """Core public symbols must exist (hard failures, not metric-based)."""
        critical = [
            ("python/auth/service.py", "AuthService"),
            ("python/auth/service.py", "validate_token"),
            ("python/auth/validators.py", "validate_claims"),
            ("python/auth/validators.py", "check_expiry"),
            ("python/payments/processor.py", "charge_card"),
            ("python/payments/gateway.py", "send_to_gateway"),
            ("python/main.py", "startup"),
            ("python/main.py", "run"),
        ]
        missing = [
            f"{fp}::{name}"
            for fp, name in critical
            if not symbol_exists(golden_storage, fp, name)
        ]
        assert not missing, f"Critical symbols missing from graph: {missing}"

    def test_dead_symbols_still_extracted(self, golden_storage: KuzuBackend) -> None:
        """Dead code symbols must still be extracted (just flagged differently)."""
        dead_symbols = [
            ("python/auth/_legacy.py", "old_validate"),
            ("python/auth/_legacy.py", "LegacyAuthProvider"),
            ("python/utils/_unused_helper.py", "dead_function_one"),
        ]
        missing = [
            f"{fp}::{name}"
            for fp, name in dead_symbols
            if not symbol_exists(golden_storage, fp, name)
        ]
        assert not missing, f"Dead module symbols not extracted: {missing}"


class TestCallEdges:
    """Call edges between symbols must match ground truth."""

    def test_call_edges_recall(self, golden_storage: KuzuBackend) -> None:
        """All expected CALLS edges exist in the graph (recall).

        Edges marked known_limitation=true are excluded from the recall
        assertion -- they document Axon's current gaps, not regressions.
        """
        data = load_expected("calls.yaml")
        score = PhaseScore("Calls")
        known_gaps: list[str] = []
        min_recall = data.get("metrics", {}).get("minimum_recall", 0.80)

        for edge in data["edges"]:
            src_file, src_name = parse_edge_ref(edge["source"])
            tgt_file, tgt_name = parse_edge_ref(edge["target"])
            found = call_edge_exists(golden_storage, src_file, src_name, tgt_file, tgt_name)

            if edge.get("known_limitation"):
                if not found:
                    known_gaps.append(
                        f"GAP: {edge['source']} -> {edge['target']}"
                        + (f"  ({edge.get('note', '')})" if edge.get("note") else "")
                    )
                # Don't count toward precision/recall -- it's a known limitation
                continue

            if found:
                score.true_positives += 1
            else:
                score.false_negatives += 1
                score.errors.append(
                    f"MISSING EDGE: {edge['source']} -> {edge['target']}"
                    + (f"  ({edge.get('note', '')})" if edge.get("note") else "")
                )

        _print_score_card([score])

        if known_gaps:
            print(f"\n[Calls] Known limitations ({len(known_gaps)}):")
            for g in known_gaps:
                print(f"  {g}")

        assert score.recall >= min_recall, (
            f"Call recall {score.recall:.1%} below minimum {min_recall:.1%}\n"
            f"Missing edges:\n"
            + "\n".join(score.errors[:5])
        )

    def test_no_false_positive_edges(self, golden_storage: KuzuBackend) -> None:
        """Declared non-edges must NOT appear in the graph (precision guard)."""
        data = load_expected("calls.yaml")
        false_positives = []

        for non_edge in data.get("non_edges", []):
            src_file, src_name = parse_edge_ref(non_edge["source"])
            tgt_file, tgt_name = parse_edge_ref(non_edge["target"])
            if call_edge_exists(golden_storage, src_file, src_name, tgt_file, tgt_name):
                false_positives.append(
                    f"FALSE POSITIVE: {non_edge['source']} -> {non_edge['target']}"
                    f"  reason: {non_edge.get('reason', 'unknown')}"
                )

        assert not false_positives, (
            "Graph contains edges that MUST NOT exist:\n"
            + "\n".join(false_positives)
        )

    def test_critical_disambiguation(self, golden_storage: KuzuBackend) -> None:
        """Same-name function disambiguation: charge_card must call auth.validate_token."""
        assert call_edge_exists(
            golden_storage,
            "python/payments/processor.py", "charge_card",
            "python/auth/service.py", "validate_token",
        ), "charge_card must call auth.service.validate_token (not auth.validators.validate)"

        # Must NOT call either of the other two validate() functions
        assert not call_edge_exists(
            golden_storage,
            "python/payments/processor.py", "charge_card",
            "python/auth/validators.py", "validate",
        ), "charge_card must NOT call auth.validators.validate"

        assert not call_edge_exists(
            golden_storage,
            "python/payments/processor.py", "charge_card",
            "python/utils/helpers.py", "validate",
        ), "charge_card must NOT call utils.helpers.validate"

    def test_cross_file_edge_preserved(self, golden_storage: KuzuBackend) -> None:
        """validate_token -> validate_claims cross-file edge must exist."""
        assert call_edge_exists(
            golden_storage,
            "python/auth/service.py", "validate_token",
            "python/auth/validators.py", "validate_claims",
        ), "validate_token must call validate_claims (cross-file)"

    def test_startup_calls_init(self, golden_storage: KuzuBackend) -> None:
        """main.startup must call auth.service.init (not utils via wildcard noise)."""
        assert call_edge_exists(
            golden_storage,
            "python/main.py", "startup",
            "python/auth/service.py", "init",
        ), "startup must call auth.service.init"
