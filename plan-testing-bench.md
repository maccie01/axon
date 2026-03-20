Was "Qualitaet" bei Codebase-Understanding bedeutet

  Axon macht 11 verschiedene Dinge. Jedes kann auf eigene Art falsch sein:

  ┌───────────────────┬────────────────────────────────────────────┬───────────────────────────────────────┐
  │       Phase       │            Was kann schiefgehen            │         Auswirkung auf Agent          │
  ├───────────────────┼────────────────────────────────────────────┼───────────────────────────────────────┤
  │ File Walking      │ Datei uebersehen oder falsch included      │ Agent weiss nicht dass Code existiert │
  ├───────────────────┼────────────────────────────────────────────┼───────────────────────────────────────┤
  │ Symbol Extraction │ Funktion/Klasse nicht erkannt              │ Agent findet Symbol nicht             │
  ├───────────────────┼────────────────────────────────────────────┼───────────────────────────────────────┤
  │ Import Resolution │ Import zeigt auf falsches Modul            │ Agent versteht Abhaengigkeiten falsch │
  ├───────────────────┼────────────────────────────────────────────┼───────────────────────────────────────┤
  │ Call Tracing      │ foo() wird falschem foo zugeordnet         │ Blast Radius komplett falsch          │
  ├───────────────────┼────────────────────────────────────────────┼───────────────────────────────────────┤
  │ Heritage          │ extends/implements nicht erkannt           │ Agent versteht Hierarchie nicht       │
  ├───────────────────┼────────────────────────────────────────────┼───────────────────────────────────────┤
  │ Type References   │ Typ-Edge fehlt oder falsch                 │ Incomplete dependency picture         │
  ├───────────────────┼────────────────────────────────────────────┼───────────────────────────────────────┤
  │ Dead Code         │ False Positive (lebendig als tot markiert) │ Agent loescht genutzten Code          │
  ├───────────────────┼────────────────────────────────────────────┼───────────────────────────────────────┤
  │ Dead Code         │ False Negative (tot als lebendig)          │ Agent ignoriert toten Code            │
  ├───────────────────┼────────────────────────────────────────────┼───────────────────────────────────────┤
  │ Search            │ Falsches Ranking                           │ Agent findet relevantes Symbol nicht  │
  ├───────────────────┼────────────────────────────────────────────┼───────────────────────────────────────┤
  │ Communities       │ Unsinnige Cluster                          │ Context-Tool liefert Rauschen         │
  └───────────────────┴────────────────────────────────────────────┴───────────────────────────────────────┘

  Das heisst wir brauchen nicht EINEN Test, sondern pro Phase eigene Accuracy-Metriken.

  Die drei Qualitaetsdimensionen

  1. Precision -- "Von allem was Axon behauptet, wieviel stimmt?"
  - Axon sagt foo ruft bar auf. Stimmt das?
  - Axon sagt _legacy_check ist Dead Code. Stimmt das?
  - Falsch-Positive sind gefaehrlich: Agent trifft Entscheidungen auf Basis falscher Daten

  2. Recall -- "Von allem was tatsaechlich existiert, wieviel findet Axon?"
  - Es gibt 50 Funktionen. Axon findet 47. Recall = 94%.
  - Die 3 fehlenden koennten kritisch sein (z.B. ein Security-Entry-Point)
  - Falsch-Negative sind gefaehrlich: Agent hat blinde Flecken

  3. Structural Correctness -- "Ist der Graph in sich konsistent?"
  - Keine verwaisten Edges (Edge zeigt auf Node der nicht existiert)
  - Keine duplizierten Nodes
  - Jeder Node hat eine File-Zuordnung
  - Kein Zyklus in EXTENDS-Edges (ausser bei Mixins)

  Design der Golden Codebase

  Das ist der Kern. Die Golden Codebase muss:
  1. Jede Beziehung deklarieren -- nicht nur "Code der funktioniert", sondern "Code wo wir EXAKT wissen was der Graph enthalten
  muss"
  2. Bewusste Edge Cases -- die Faelle wo Parser typischerweise scheitern
  3. Negative Assertions -- Beziehungen die NICHT im Graph sein duerfen
  4. Multi-Language -- Python + TypeScript, weil Axon beides kann
  5. Self-contained -- keine externen Deps die sich aendern
  6. Versioniert -- die Expected-Output-Files sind Teil des Repos

  Struktur

  tests/golden/
    codebase/                      # Die synthetische Codebase
      python/
        auth/
          __init__.py
          service.py               # Authentication logic
          validators.py            # Input validation
          _legacy.py               # Intentionally dead module
        payments/
          __init__.py
          processor.py             # Calls auth.service
          gateway.py               # External API connector
        utils/
          helpers.py               # Shared utilities
          _unused_helper.py        # Dead code
        main.py                    # Entry point
      typescript/
        api/
          index.ts                 # Barrel export
          routes.ts                # HTTP handlers
          middleware.ts             # Auth middleware
        shared/
          types.ts                 # Shared types
          constants.ts             # Dead export test
        app.ts                     # Entry point

    expected/                      # Ground Truth (YAML)
      symbols.yaml                 # Every symbol, type, location
      calls.yaml                   # Every call edge (and non-edges)
      imports.yaml                 # Every import resolution
      heritage.yaml                # extends/implements
      types.yaml                   # USES_TYPE edges
      dead_code.yaml               # Exact dead code list
      communities.yaml             # Expected cluster groupings
      search_queries.yaml          # Query -> expected top results

    test_golden.py                 # Runs pipeline, compares to expected
    test_invariants.py             # Property-based structural checks
    test_search.py                 # Search quality benchmarks
    conftest.py                    # Shared fixtures

  Expected YAML Format

  # expected/calls.yaml
  edges:
    # MUST exist (true positives)
    - source: "python/auth/service.py::validate_token"
      target: "python/auth/validators.py::check_expiry"
      confidence: ">= 0.8"

    - source: "python/payments/processor.py::charge_card"
      target: "python/auth/service.py::validate_token"
      confidence: ">= 0.7"

    # Cross-file with common name
    - source: "python/main.py::startup"
      target: "python/auth/service.py::init"
      note: "Must NOT resolve to utils/helpers.py::init"

  non_edges:
    # MUST NOT exist (false positive detection)
    - source: "python/payments/processor.py::charge_card"
      target: "python/utils/helpers.py::validate"
      reason: "Different validate() -- payments uses auth.validators"

    - source: "python/auth/service.py::validate_token"
      target: "python/auth/_legacy.py::old_validate"
      reason: "Legacy module is never imported"

  metrics:
    minimum_precision: 0.95
    minimum_recall: 0.90

  Die bewussten Edge Cases

  Ich wuerde diese Faelle einbauen -- jeder einzelne ist ein bekannter Schwachpunkt von statischen Analysern:

  Python Edge Cases:
  - Gleicher Funktionsname in verschiedenen Modulen (validate() in auth UND payments)
  - from module import * (wildcard imports)
  - Decorator-wrapped Functions (@app.route, @property)
  - Closures und nested Functions
  - super() Calls in Vererbungsketten
  - Conditional Imports (if TYPE_CHECKING:)
  - Re-exports via __init__.py
  - self/cls Method Calls (Axon hatte hier Bug #34)
  - __all__ Export Lists (beeinflusst Dead Code Detection)
  - Async/await Patterns
  - Classmethod vs Staticmethod vs Property
  - Multiple Inheritance (MRO)
  - Protocol/ABC Conformance (Dead Code False Positives)

  TypeScript Edge Cases:
  - Barrel Exports (export * from './module')
  - Type-only Imports (import type { Foo })
  - Overloaded Functions
  - CommonJS vs ESM (require vs import)
  - Namespace Imports (import * as utils)
  - Default + Named Exports
  - Declaration Merging
  - Optional Chaining in Calls (obj?.method())
  - Generic Type References (Array<User>)

  Cross-Cutting:
  - Circular Dependencies (A imports B imports A)
  - Diamond Dependency (A->B->D, A->C->D)
  - Dead Module (importiert von niemandem)
  - Dead Function in lebendigem Modul
  - "Almost Dead" (nur von Tests importiert)

  Wie der Test Runner funktioniert

  # tests/golden/test_golden.py (Konzept)

  def test_symbol_extraction(golden_graph, expected_symbols):
      """Every declared symbol exists in the graph with correct type."""
      found = query_all_symbols(golden_graph)
      for expected in expected_symbols:
          match = find_symbol(found, expected.name, expected.file)
          assert match, f"Missing symbol: {expected.name} in {expected.file}"
          assert match.type == expected.type
      # Check for unexpected symbols (noise)
      assert len(found) <= len(expected_symbols) * 1.1  # Max 10% extra

  def test_call_edges(golden_graph, expected_calls):
      """Every declared call edge exists. No declared non-edges exist."""
      precision_hits = 0
      recall_hits = 0
      for edge in expected_calls.edges:
          exists = graph_has_edge(golden_graph, edge.source, edge.target, "CALLS")
          assert exists, f"Missing CALLS edge: {edge.source} -> {edge.target}"
          recall_hits += 1
      for non_edge in expected_calls.non_edges:
          exists = graph_has_edge(golden_graph, non_edge.source, non_edge.target, "CALLS")
          assert not exists, f"False positive: {non_edge.source} -> {non_edge.target}"
      # Report metrics
      report_metrics("calls", precision_hits, recall_hits, ...)

  def test_dead_code(golden_graph, expected_dead):
      """Exact match: no false positives, no false negatives."""
      actual_dead = query_dead_code(golden_graph)
      expected_set = set(expected_dead.symbols)
      actual_set = set(actual_dead)
      false_positives = actual_set - expected_set
      false_negatives = expected_set - actual_set
      assert not false_positives, f"False positives: {false_positives}"
      assert not false_negatives, f"False negatives: {false_negatives}"

  Invariant Tests (Property-Based)

  Diese laufen auf JEDER Codebase, nicht nur der Golden:

  # tests/golden/test_invariants.py (Konzept)

  def test_no_orphaned_edges(graph):
      """Every edge endpoint exists as a node."""
      edges = query_all_edges(graph)
      nodes = query_all_node_ids(graph)
      for edge in edges:
          assert edge.source_id in nodes
          assert edge.target_id in nodes

  def test_no_duplicate_nodes(graph):
      """No two nodes share the same ID."""
      ids = query_all_node_ids(graph)
      assert len(ids) == len(set(ids))

  def test_every_symbol_has_file(graph):
      """Every Function/Class/Variable node has a file_path."""
      symbols = query_all_symbols(graph)
      for s in symbols:
          assert s.file_path, f"Symbol {s.name} has no file"
          assert s.line_number > 0

  def test_extends_acyclic(graph):
      """No cycles in inheritance (except known patterns)."""
      extends = query_edges_by_type(graph, "EXTENDS")
      assert not has_cycle(extends)

  def test_imports_resolve_to_existing_files(graph):
      """Every IMPORTS edge target is a file that exists in the graph."""
      imports = query_edges_by_type(graph, "IMPORTS")
      files = query_all_files(graph)
      for imp in imports:
          assert imp.target in files

  Search Quality Benchmarks

  # expected/search_queries.yaml
  queries:
    - query: "validate_token"
      expected_top_3:
        - "python/auth/service.py::validate_token"
        - "python/auth/validators.py::check_expiry"  # Related
      must_not_appear_top_5:
        - "python/utils/helpers.py::validate"  # Wrong validate

    - query: "payment processing"
      expected_top_3:
        - "python/payments/processor.py::charge_card"
        - "python/payments/gateway.py::send_to_stripe"
      note: "Natural language query -- vector search should help here"

    - query: "dead code in auth"
      expected_top_3:
        - "python/auth/_legacy.py::old_validate"

  Wie das in den Workflow passt

  1. Baue Golden Codebase + Expected YAML  (einmalig)
  2. Laufe `pytest tests/golden/`           (nach jedem Change)
  3. Output: Precision/Recall/F1 pro Phase  (Score Card)
  4. CI blockiert PR wenn Score sinkt        (Quality Gate)

  Score Card Beispiel

  Axon Quality Report (v0.2.3, golden-codebase v1)
  ================================================
  Phase            Precision  Recall   F1     Status
  Symbols          98.2%      96.5%    97.3%  PASS
  Calls            91.4%      87.2%    89.3%  WARN (< 90%)
  Imports          99.1%      98.7%    98.9%  PASS
  Heritage         100%       95.0%    97.4%  PASS
  Dead Code        88.5%      92.3%    90.4%  WARN
  Search (code)    --         85.0%    --     WARN
  Search (NL)      --         70.0%    --     FAIL (< 75%)
  Invariants       14/14 pass               PASS
  ================================================
  Overall: 7/9 PASS, 2 WARN, 0 FAIL

  Was ich vorschlage

  1. Ich baue die Golden Codebase mit ~25-30 Files (Python + TypeScript), bewusst alle Edge Cases oben abgedeckt
  2. Ich schreibe die Expected YAML Files mit exakter Ground Truth
  3. Ich baue den Test Runner der Precision/Recall/F1 pro Phase reported
  4. Ich baue die Invariant Tests
  5. Wir laufen es gegen den aktuellen Axon v0.2.3 -- das gibt uns die Baseline
  6. Jede Phase-Aenderung wird gegen die gleiche Golden Codebase getestet

Das Problem mit echten Codebases

  Du kannst die Ground Truth nicht definieren ohne sie manuell zu verifizieren. Das bedeutet:

  1. Du muesstest JEDE Call-Edge in scribolous oder axon per Hand pruefen ("ruft charge_card wirklich validate_token auf?
  Ja/Nein")
  2. Du muesstest JEDE "Non-Edge" identifizieren ("ruft charge_card NICHT old_validate auf?") -- das ist bei echtem Code quasi
  unmoeglich, weil du nicht weisst was du nicht weisst
  3. Bei jeder Code-Aenderung am Projekt aendert sich die Ground Truth -- du baust auf Sand

  Aber -- echte Codebases haben Muster die synthetische nicht haben. Vendor-Code, Auto-Generated Files, Framework-Magie,
  Django/Express-Patterns.

  Der beste Ansatz: Beides

  tests/golden/                    # Synthetisch -- ACCURACY
    codebase/                      # 25-30 Files, Python + TS
    expected/                      # Exakte Ground Truth
    test_accuracy.py               # Precision/Recall/F1

  tests/regression/                # Axon auf sich selbst -- STABILITY
    test_self_index.py             # Indexiere Axon's eigenen Code
    test_invariants.py             # Structural correctness checks
    baseline_snapshot.json         # Eingefrorener Stand (Symbolcount, Edgecount)
