To build the "ultimate" version of Axon, your fork (`maccie01/axon`) should act as the master aggregator. You already have the best architectural roadmap (via your `CLAUDE.md` P0/P1 issue tracker), so the next step is absorbing the best functional implementations from the community and hardening the project with modern Python tooling.

Here is a detailed, multi-phase plan to upgrade your fork into a production-ready, enterprise-grade code intelligence engine.

---

### Phase 1: The "Super-Fork" Merge (Cherry-Picking)
Before adding new tools, you should integrate the high-value logic mapped out by other contributors.

**1. From `zack381/axon` (The Extensibility & Accuracy Update)**
*   **Take the Parsers:** Cherry-pick the PHP, HTML, and JSX/React tree-sitter parsers (`PR #15`, `PR #14`).
*   **Take the Dead-Code Overhaul:** Merge `PR #17` (Reduced dead code false positives by 83%) and `PR #25` (Fix TS enums, implicit interface methods, framework exemptions). This dramatically improves the signal-to-noise ratio for AI agents.
*   **Take the Symbol Resolution Fixes:** Merge `PR #30` (normalized parent dir paths) and `PR #22` (window exports and path-proximity matching). This directly solves some of the P1 "Call Resolution Wrong" issues you noted in your `CLAUDE.md`.

**2. From `rosschurchill/axon` (The Security Hardening)**
*   **Take the Security Patch:** Cherry-pick `PR #26` (22 security findings + 45 new tests). Since Axon executes locally and parses arbitrary code, hardening it against path traversal, regex denial-of-service (ReDoS), and malicious symlinks is critical before running it in a local background watch mode.

**3. From `spark-cjbot/axon` & `ajeetrix/axon` (Language Expansion)**
*   **Take the Parsers:** Merge `PR #18` (C# AST support) and `PR #6` (Go support) to make Axon a truly polyglot engine.

---

### Phase 2: Internal Tooling & Code Quality (Dependencies)
To ensure the codebase doesn't collapse under its own weight as you add languages and features, you need to modernize Axon's internal Python toolchain.

*   **Ruff (Linting & Formatting):** Replace `flake8`, `black`, and `isort` with `ruff`. It is 10-100x faster and can automatically fix hundreds of common code smells. Add it to `pyproject.toml` and run it on CI.
*   **Pyright or Mypy (Strict Type Checking):** A graph engine is highly structured. You should enforce strict typing for AST nodes, edges, and Database payloads. `Pyright` is generally faster and smarter for complex generics.
*   **Pre-commit:** Implement a `.pre-commit-config.yaml` that runs Ruff, Pyright, and basic checks (like preventing large file commits or trailing whitespace) automatically before every commit.
*   **Pydantic v2:** If Axon isn't using it heavily already, use Pydantic to validate the Graph nodes, edges, and MCP Tool inputs. This provides bulletproof validation against AI agents hallucinating bad parameters.
*   **pytest-xdist & pytest-cov:** As the test suite grows (especially with `rosschurchill`'s 45 new tests), use `pytest-xdist` to run tests in parallel, and `pytest-cov` to enforce a minimum test coverage threshold.

---

### Phase 3: Base Open-Source Tools to Integrate (Engine Completeness)
Tree-sitter and KuzuDB are great, but relying *only* on syntactical parsing (Tree-sitter) creates limitations (like your issue #3: "Call Resolution Wrong on Common Function Names"). Here are the base OSS tools you should integrate into Axon's architecture:

**1. `ast-grep` (sg)**
*   **Why:** Tree-sitter gives you an AST, but traversing it in pure Python is slow. `ast-grep` is a blazing-fast CLI tool built on top of Tree-sitter that allows you to search code using code patterns.
*   **Integration:** You can use `ast-grep` as a fast pre-filter for your ingestion pipeline or expose an MCP tool `ast_search` directly to the AI agent so it can query structural patterns instantly without hitting KuzuDB.

**2. Language Server Protocol (LSP) Wrappers (e.g., `pygls` or `multilspy`)**
*   **Why:** Tree-sitter is *syntactic* (it knows `get()` is a function call). LSP is *semantic* (it knows `get()` belongs to `my_app.auth.validators`). Your `CLAUDE.md` issue #3 is impossible to solve perfectly with Tree-sitter alone.
*   **Integration:** Run lightweight headless language servers (like `pyright` for Python, `tsserver` for TS) in the background. Ask the LSP for "Go to Definition" or "Find References" to draw 100% accurate caller/callee edges in KuzuDB, falling back to Tree-sitter only when the LSP fails.

**3. `rustworkx` (High-Performance Local Graph Analysis)**
*   **Why:** KuzuDB is great for querying, but if the AI agent asks "What is the shortest execution path between Auth.login and Database.drop?", calculating that might be slow.
*   **Integration:** Load critical execution subgraphs into `rustworkx` (a Rust-based graph algorithm library for Python) to instantly calculate shortest paths, centrality, and blast-radius bottlenecks.

**4. `Watchfiles` (Rust-based File Watching)**
*   **Why:** Your `CLAUDE.md` issue #2 notes that Watch Mode re-runs the full pipeline every 30s.
*   **Integration:** Replace the current polling mechanism with `watchfiles` (built on notify in Rust). It uses native OS APIs (FSEvents/kqueue/inotify) to instantly detect single-file changes. You can then trigger an *incremental* graph update (DETACH DELETE only the changed file's node, parse the new file, MERGE the new edges).

---

### Phase 4: Action Plan / Execution Roadmap

**Step 1: The Typer/CLI & Security Overhaul (Days 1-2)**
1. Implement `execute_parameterized()` in `kuzu_backend.py` to fix your P0 Cypher Injection vulnerability.
2. Setup `ruff`, `pyright`, and `pre-commit` in the base repo. Auto-format the whole codebase.
3. Merge `rosschurchill/axon`'s security PR.

**Step 2: The Multi-Language Aggregation (Days 3-5)**
1. Merge `zack381`'s Dead-Code PRs first (they are Python/TS specific and highly valuable).
2. Merge the PHP, HTML, JSX, C#, and Go parsers from the respective forks.
3. Run `pytest` to ensure the extended AST rules don't break the existing Python/TS pipeline.

**Step 3: Fix the Watcher (Days 6-7)**
1. Swap the 30s polling loop for `watchfiles`.
2. Rewrite `run_pipeline` to accept a `file_path` list. When a file changes, remove only its nodes from KuzuDB and re-ingest just that file, reducing the 30s-60s blocking window to <0.5 seconds.

**Step 4: Semantic Graph Upgrade (Next Iteration)**
1. Begin experimenting with integrating a headless LSP or `ast-grep` into the symbol resolution phase (`calls.py:164-178`) to fix the "shortest file path" tiebreaker bug identified in your `CLAUDE.md`.

If you want to move Axon from a "good local static analysis tool" to a "state-of-the-art semantic code intelligence engine," you have to break the barrier of purely syntactic (AST-based) parsing.

To drastically improve it, you need to transition Axon into a **hybrid Neuro-Symbolic architecture**—combining deterministic graph traversal (Symbolic) with modern Machine Learning and LLMs (Neuro).

Here is the blueprint for a drastic improvement, categorized by the technologies you should integrate into your roadmap:

---

### 1. Upgrade from Tree-sitter ASTs to "Code Property Graphs" (CPG)
Right now, Axon maps files, classes, and functions using Tree-sitter. This is basically an Abstract Syntax Tree (AST) loaded into KuzuDB.

To drastically improve dependency tracking, you must upgrade the data model to a **Code Property Graph (CPG)**.
*   **What it is:** A CPG combines an AST, a Control Flow Graph (CFG), and a Program Dependence Graph (PDG) into one unified database.
*   **Why it matters:** Instead of just knowing that `Function A` calls `Function B`, a CPG knows *under what conditions* `Function A` calls `Function B` (Control Flow), and what variables carry data from A to B (Data Flow).
*   **How to integrate:** Use an existing open-source CPG generator like **Joern** (by ShiftLeft) or **Semantic/Stack Graphs** (by GitHub). You run these engines to generate the CPG nodes/edges, and then bulk-load *that* data into KuzuDB instead of raw Tree-sitter dumps.

### 2. Semantic Code Embeddings (GraphCodeBERT / UniXcoder)
Currently, Axon relies heavily on BM25 (text search) and fuzzy string matching for node resolution. If a user defines `def fetch_data()` and someone else searches for `get_records()`, Axon might fail to link them semantically.

*   **The Upgrade:** Integrate a model specifically pre-trained on code and its underlying ASTs, such as Microsoft's **GraphCodeBERT** or **UniXcoder**.
*   **How it works:** GraphCodeBERT takes the source code *and* the data flow edges as input to generate its vector embeddings.
*   **Implementation:** During the pipeline's ingestion phase, pass every function and class through GraphCodeBERT (running locally via `sentence-transformers` or ONNX). Store the resulting 768-dimensional float arrays as properties on your KuzuDB nodes.
*   **Result:** The AI agent can now do pure semantic vector searches: *"Find the function that authenticates the database user,"* and KuzuDB will return the exact node, even if the words "authenticate," "database," or "user" are not in the function name.

### 3. Graph Neural Networks (GNNs) for Link Prediction
Your `CLAUDE.md` noted a P1 issue: "Call Resolution Wrong on Common Function Names" (e.g., `get()` resolves to the wrong target file). Tree-sitter doesn't know the types, so it guesses based on shortest paths.

*   **The Upgrade:** Use a **Graph Neural Network (GNN)**, specifically GraphSAGE or Graph Attention Networks (GAT), to perform **Link Prediction**.
*   **How it works:** A GNN learns the "neighborhood" of a node. If you have a call to `user.get()`, the GNN looks at the surrounding code, the variables passed into it, and the file context. It compares that context to all the `get()` definitions in the codebase and assigns a probability score to the edge.
*   **Integration:** You can use **PyTorch Geometric (PyG)**. When the Tree-sitter parser encounters an ambiguous call (like `get()`), it creates an "unresolved" edge. PyG runs a quick inference pass over KuzuDB and updates the edge with the correct target node based on the highest probability.

### 4. Headless Language Server Protocol (LSP) as a Fallback Resolver
While GNNs are probabilistic, developers sometimes need deterministic certainty (100% accuracy).

*   **The Upgrade:** Run a headless LSP (like `pyright` for Python or `tsserver` for TypeScript) via a Python wrapper like `multilspy`.
*   **Integration:** During the pipeline phase where you connect `CALLS` edges, if Tree-sitter finds an ambiguous call, Axon queries the background LSP: *"Hey Pyright, what is the exact definition of `get()` on line 42?"* The LSP returns the exact file and line number, allowing Axon to draw a mathematically perfect edge in KuzuDB.

### 5. GraphRAG (Retrieval-Augmented Generation over Graphs)
To make Axon the ultimate tool for Claude/AI Agents, you must format the KuzuDB output for LLM consumption.

*   **The Upgrade:** Implement **GraphRAG** (a concept popularized by Microsoft).
*   **How it works:** When an AI agent asks a complex architectural question via MCP, Axon doesn't just return a list of nodes. It runs a graph traversal, detects "communities" of tightly coupled code (using algorithms like Louvain community detection), and uses a local LLM to generate summaries of those sub-graphs.
*   **Result:** Instead of giving Claude 50 raw function definitions, Axon returns: *"The `Auth` module consists of 12 functions. The critical path involves `validate_token()`, which if changed, breaks 3 downstream APIs in the `Billing` service."*

---

### The Ultimate Architecture Stack (Summary)

If you implemented this, Axon would move from Alpha to Enterprise-Grade:

1.  **Parsing Layer:** Tree-sitter (Fast syntax) + **Joern/Semantic** (Code Property Graphs).
2.  **Resolution Layer:** **Headless LSPs** (Deterministic semantic linking) + **PyTorch Geometric GNNs** (Probabilistic link prediction for dynamic languages).
3.  **Vector Embedding:** **GraphCodeBERT / UniXcoder** (AST-aware semantic vectors).
4.  **Storage Engine:** **KuzuDB** (handling both Graph Topology and Vector Similarity Search simultaneously).
5.  **Output Layer:** **GraphRAG / Community Detection** (Summarizing subgraph blast-radiuses for AI agent consumption).
You are absolutely right. If we step back, the current architecture of Axon (and most basic code analysis tools) relies on a fundamental flaw: **Syntactic Guessing**.

Right now, Axon uses Tree-sitter to build a syntax tree, and then relies on handcrafted Python scripts to manually walk that tree and "guess" symbol scope, imports, and cross-file relationships (which leads to the exact bug you highlighted in `CLAUDE.md`: vendored `a/b.py:get()` overriding `src/validators.py:get()`). This is inherently fragile, slow, and computationally inefficient.

To make the architecture **drastically smarter and more efficient**, we must abandon manual AST traversal and adopt **Semantic Code Protocols** and **Code Property Graphs (CPG)**.

Here is the blueprint for a next-generation, high-performance architecture for Axon.

---

### 1. The Core Paradigm Shift: From AST to SCIP / LSIF
Instead of trying to reverse-engineer scoping rules in Python, Axon should consume an open standard designed specifically for cross-file semantic intelligence.

**The Tool: SCIP (Semantic Code Intelligence Protocol by Sourcegraph)**
*   **What it is:** SCIP is a lightweight protobuf standard that represents a perfect, resolved semantic graph of a codebase.
*   **How it works:** Instead of Axon parsing TS/Python with Tree-sitter, you run `scip-typescript` or `scip-python`. These indexers hook directly into the language's native type-checker/compiler. They resolve every single symbol (variables, methods, classes) with 100% accuracy, even across complex inheritance, monorepos, and dynamic imports.
*   **Why it’s smarter:** It completely eliminates your `get()` resolution bug. SCIP assigns a unique, globally distinct URI to every symbol (e.g., `scip-python python core 0.1 my_app/auth/validators/get().`).
*   **The Efficiency Win:** Axon simply reads the `.scip` protobuf file and does a 1-to-1 bulk load directly into KuzuDB. You delete thousands of lines of fragile Python parsing code, and ingestion becomes instantaneous.

### 2. Zero-Build Semantic Resolution: GitHub's Stack Graphs
If you want to maintain Axon's ability to index a codebase *without* requiring the user to install language toolchains (which SCIP sometimes requires), you should integrate **Stack Graphs**.

*   **The Tool:** `tree-sitter-graph` / GitHub Stack Graphs (written in Rust).
*   **What it is:** This is the exact technology GitHub uses to power "Click to Go to Definition" and "Find References" in the browser without spinning up an LSP or compiling the code.
*   **How it works:** It uses Tree-sitter but adds a mathematical framework called a "Stack Graph." It pushes and pops scope frames as it parses, creating a graph where paths between nodes represent valid name bindings.
*   **The Efficiency Win:** It resolves cross-file dependencies entirely via graph reachability algorithms. You can run this in a background Rust thread, and it will effortlessly map the exact caller/callee relationships with perfect scoping rules, taking milliseconds per file.

### 3. Understanding Execution Flow: Code Property Graphs (CPG)
If an AI agent needs to understand "Blast Radius" or "Dead Code," simple Call Graphs are not enough. You need Data Flow Graphs (DFG) and Control Flow Graphs (CFG).

*   **The Tool:** **Joern / ShiftLeft Ocular** or integrating LLVM/MLIR-style passes.
*   **What it is:** A Code Property Graph merges the AST, CFG, and DFG into a single interconnected graph.
*   **Why it’s smarter:** If an AI agent asks, *"If I change the password validation logic, what database endpoints are affected?"*, an AST/Call graph can't answer this if the data is passed dynamically through generic wrappers. A CPG tracks the *flow of variables* (Data Flow), allowing KuzuDB to traverse "Taint Analysis" paths.

### 4. Rewriting the Orchestration Layer in Rust (PyO3)
Python is the wrong language for the heavy lifting of a local graph-intelligence engine. Your `CLAUDE.md` notes that Watch Mode hangs the server for 30-60 seconds on large codebases.

*   **The Solution:** Move the operational layer (File Watching, Tree-sitter/SCIP parsing, and Graph Diffing) to **Rust**.
*   **How it works:**
    1. Use Rust's `notify` crate for hyper-efficient, OS-level file watching.
    2. When `auth.py` changes, Rust instantly re-indexes *only* that file using Stack Graphs or SCIP.
    3. Rust calculates the exact graph diff (Nodes deleted, Edges added) and updates KuzuDB directly via its C++ API.
    4. You expose this Rust core to your Python MCP server via `PyO3`.
*   **The Result:** Watch mode graph updates drop from 30 seconds to **<50 milliseconds**. The MCP server never hangs.

### 5. Smarter Vector/Semantic Architecture
Currently, Axon likely generates an embedding for every function and stores it. This is slow to generate and hard to sync.

*   **The Tool:** **LanceDB** or **DuckDB-vss** combined with ONNX.
*   **The Smarter Approach:** Instead of using an external Python embedding library, embed the `ONNXRuntime` directly into your Rust core using a quantized, highly efficient model like `BGE-micro` or `Nomic-Embed`.
*   **Hybrid Querying:** Store the structural graph in KuzuDB, but use LanceDB for the vector data. Map the KuzuDB Node IDs to LanceDB Vector IDs. When the AI agent searches "Authentication logic", LanceDB instantly returns the top 5 Node IDs, which you then pass to KuzuDB to fetch the surrounding blast-radius graph.

---

### The Ultimate "Axon v2" Architecture Blueprint

If I were architecting this to be the definitive local code intelligence engine for Claude/AI Agents, this is the stack:

1.  **Ingestion Protocol:** Rip out manual Python Tree-Sitter parsers. Integrate **SCIP Indexers** (for heavy semantic truth) and fallback to **GitHub Stack Graphs** (for zero-config dynamic languages).
2.  **Engine Core:** **Rust**. It handles filesystem watching, parsing SCIP protobufs, and generating graph diffs. It runs as a highly concurrent background daemon.
3.  **Knowledge Graph:** Keep **KuzuDB** (it's built in C++ and blazing fast). The Rust core talks to KuzuDB natively, sending incremental `MERGE` and `DETACH DELETE` commands for single-file changes.
4.  **Vector Store:** **LanceDB** (Rust-native, zero-copy, serverless) strictly for semantic vector search, mapped to KuzuDB's Node IDs.
5.  **Agent Interface (MCP):** A thin Python wrapper using `PyO3` that serves the MCP endpoints to Claude. It doesn't do any heavy lifting; it just translates natural language into KuzuDB Cypher/LanceDB queries.

**Why this is drastically better:**
*   **Accuracy:** You stop guessing scoping rules. SCIP/Stack Graphs provide compiler-level semantic accuracy.
*   **Speed:** Moving orchestration to Rust and using incremental graph patches means the graph is always real-time. No 30-second locking rebuilds.
*   **Simplicity:** You offload the hardest part of code intelligence (building parsers for every language's weird quirks) to open-source standards (SCIP/Tree-sitter Stack Graphs) maintained by Sourcegraph and GitHub.
It does not replace it; it **fuses** with it into a layered, multimodal approach.

Your insight hits on the exact frontier of AI engineering right now. If we just throw raw source code at an LLM, it hallucinates connections and wastes tokens. If we just use static analysis (like the current iteration of Axon), we get rigid, mathematically perfect maps that lack any understanding of *why* the code exists or what the *business intent* is.

The ultimate goal you are describing is a **"Neuro-Symbolic" architecture**—a layered approach where static analysis (the symbolic) provides the rigid scaffolding, and the LLM (the neural) provides the semantic flesh, and both are exposed to an autonomous agent to iterate on the codebase.

Here is how those layers come together to create the exact system you are envisioning:

### Layer 1: The Symbolic Foundation (The "Bones")
We cannot discard static analysis. LLMs are probabilistic; they guess. If an AI agent is going to automate refactoring or security patching across a 5-million-line codebase, it cannot guess if `Function A` calls `Function B`. It needs mathematical proof.

*   **The Tools:** Tree-sitter (ASTs), Code Property Graphs (CPGs), and SCIP (Semantic Code Intelligence Protocol).
*   **The Output:** A rigid, 100% accurate graph (stored in KuzuDB or Neo4j) that tracks every exact definition, import, control flow, and data taint path.
*   **The Agent's Use Case:** The agent uses this layer to verify safety. *"If I change the DB adapter here, give me the exact mathematical list of every downstream file that will break."*

### Layer 2: The Semantic Intent Model (The "Flesh")
This is where your vision comes to life. We layer LLM-generated semantic understanding *on top* of the rigid graph.

*   **The Tools:** Local, fast LLMs (like Qwen-Coder or Llama-3) running in parallel.
*   **The Output:** "Token-Optimized Semantic Skeletons" (TOSS). As discussed, we take the rigid AST nodes from Layer 1 and use the LLM to generate 1-2 sentence business logic summaries for every node.
*   **The Agent's Use Case:** The agent uses this layer for cognitive navigation. *"I need to fix a bug in the shopping cart tax calculation."* It searches the semantic layer to instantly find the relevant skeleton without reading 10,000 lines of boilerplate.

### Layer 3: The Verification & Iteration Engine (The "Immune System")
An autonomous agent needs to know if its proposed changes actually work. It can't just read the graph; it has to interact with the environment.

*   **The Tools:** Linters (Ruff), Type Checkers (Pyright), Test Runners (pytest), and Security Scanners (Bandit/Semgrep).
*   **The Output:** Binary pass/fail signals with specific error outputs.
*   **The Agent's Use Case:** The agent writes the code, but before committing, it queries Layer 3. If Ruff flags a syntax error, or Pyright flags a type mismatch, the agent reads the error, cross-references Layer 1 to see the impact, and iterates on its code until it passes.

### How it all comes together for the LLM (The MCP Format)

To make this accessible to the LLM (like Claude or a custom Agent), we expose these layers not as raw databases, but as **Interactive Topographical Tools** (via the Model Context Protocol - MCP).

When the LLM is given a ticket: *"Refactor the authentication flow to use OAuth2,"* here is how it uses the layered system:

1.  **Orient:** The agent calls `get_semantic_map(topic="authentication")`. Layer 2 returns the heavily compressed, LLM-generated business logic summaries of the Auth module. The LLM instantly understands the layout.
2.  **Pinpoint:** The agent calls `get_exact_dependencies(node="src/auth/login.py:verify_password")`. Layer 1 (the static analysis graph) returns the 100% accurate list of the 4 files that rely on this function.
3.  **Draft:** The agent drafts the code changes in its context window.
4.  **Verify:** The agent calls `verify_change(files=["src/auth/login.py"])`. Layer 3 runs Ruff, Pyright, and the unit tests.
5.  **Iterate:** If Layer 3 returns a type error (e.g., `Expected string, got UserObject`), the agent uses Layer 1 to look up the exact `UserObject` definition, corrects its code, and runs the verification again.

### Conclusion: It's an Evolution, Not a Replacement

This architecture doesn't replace Axon; it **evolves Axon into the backend engine**.

Currently, Axon is trying to be the *entire* tool. In this new paradigm, Axon (with its Tree-sitter parsers and KuzuDB graph) becomes **Layer 1**. You then build the parallel LLM summarization pipeline (Layer 2) and the verification toolchain (Layer 3) on top of it, creating a comprehensive "brain" that an AI Agent can plug into to safely and autonomously engineer software at any scale.
Ah, I see what you did there! `maccie01/CodeLynx` is actually **your ongoing thesis project** (*"LLMs als neue Generation der statischen Codeanalyse"*), and you already have an extensive research catalog covering exactly this: SAST-LLM integration, Agent Systems, RAG for code, and vulnerability detection.

To answer your question: **No, it does not replace Axon. You are absolutely right—it is a layered approach.**

My previous brainstorm (the "Fractal Intent Graph") is essentially describing the theoretical architecture of what **CodeLynx** aims to be. Axon is not the competitor to CodeLynx; Axon is the underlying *engine* that a framework like CodeLynx would use as its foundation.

Here is exactly how this layered architecture comes together, merging traditional static analysis (Axon) with LLM-driven verification (CodeLynx):

### The Layered Architecture (How Axon and CodeLynx Fit Together)

You cannot replace traditional static analysis with LLMs because LLMs hallucinate, have context window limits, and are computationally expensive. Conversely, static analysis tools (SAST) generate too many false positives and cannot understand "business intent."

The modern approach is a **symbiotic, multi-layered stack**:

#### Layer 1: The Deterministic Substrate (Axon / Static Analysis)
*   **What it does:** Uses Tree-sitter, ASTs, and Code Property Graphs (CPGs) to extract the absolute, unarguable truth of the codebase.
*   **Output:** "Function A calls Function B. Variable X flows into SQL Query Y."
*   **Role in the system:** It acts as the "eyes and ears" (the sensors). It cheaply and instantly maps the topological structure of the code, detecting dead code, call chains, and basic syntax issues.

#### Layer 2: The Translation & Compression Layer
*   **What it does:** LLMs choke on raw JSON graphs and massive files. This layer takes the deterministic graph from Axon and transforms it into highly optimized, LLM-native formats (what I called "Token-Optimized Skeletons" or what your research likely covers under code representation).
*   **Output:** Markdown-formatted stubs, localized execution paths, and focused context windows.

#### Layer 3: The Semantic & Cognitive Layer (CodeLynx / LLM Agents)
*   **What it does:** This is where your CodeLynx framework lives. It takes the optimized structural data from Layer 2 and applies Large Language Models to infer **business logic, complex anti-patterns, and logical vulnerabilities**.
*   **How it works:** The LLM doesn't have to read the whole codebase to find a bug. It queries the Axon graph: *"Give me the slice of the graph that handles Database Authentication."* Axon returns just that slice. The LLM then analyzes that specific slice for business-logic flaws (e.g., "This skips password hashing if the user is an admin").

#### Layer 4: The Iterative Verification Loop
*   **What it does:** The LLM agent acts autonomously to fix the code.
*   **The Loop:**
    1. CodeLynx (LLM) spots a security vulnerability.
    2. It writes a patch.
    3. It asks Axon to instantly re-parse the changed file.
    4. Axon updates the graph and runs a quick deterministic check (e.g., "Did this break the downstream call graph?").
    5. CodeLynx verifies the fix is both semantically correct and structurally sound.

### Summary: The Ultimate Synergy

You shouldn't try to make Axon "smarter" by cramming LLMs directly into its core parser. Axon should remain a blazing-fast, dumb, deterministic graph engine (using Tree-sitter, KuzuDB, and maybe eventually SCIP/CPGs).

**CodeLynx** sits on top of Axon. CodeLynx is the multi-agent system that knows *how to ask Axon the right questions*, consuming Axon's structural data to perform deep security verification, architecture review, and automated refactoring.

In the context of your thesis, Axon is the perfect proof-of-concept backend tool that proves traditional AST data can be exposed to LLM agents (via MCP) to bridge the gap between static analysis and artificial intelligence!
Here is the objective architectural plan for evolving the CodeLynx ecosystem, strictly dividing responsibilities between the foundational graph engine (Axon) and the higher-order reasoning framework (CodeLynx).

### 1. Architectural Boundaries

The system must be split into two discrete, decoupled layers.

#### Layer 1: Axon (The Deterministic Substrate)
**Role:** High-speed, language-agnostic code ingestion, indexing, and deterministic querying. It computes topological facts, not semantic meaning.
**Scope:**
*   **Parsing & AST Generation:** Converting raw source code (Python, TS, C#, Go) into uniform ASTs via Tree-sitter.
*   **Graph Construction:** Mapping syntax to a graph schema (Nodes: Files, Classes, Functions; Edges: CALLS, IMPORTS, EXTENDS).
*   **Storage:** Maintaining the graph state in KuzuDB.
*   **Deterministic Analysis:** Computing topological metrics (e.g., dead code via reachability, execution paths via shortest-path algorithms).
*   **API/Interface:** Exposing deterministic endpoints (via Model Context Protocol - MCP) for graph traversal and raw code retrieval.

#### Layer 2: CodeLynx (The Cognitive Framework)
**Role:** Multi-agent reasoning, semantic analysis, and security verification. It consumes Axon's topological facts to infer business logic and vulnerabilities.
**Scope:**
*   **Agent Orchestration:** Managing specialized LLM agents (e.g., Security Auditor, Refactoring Specialist, Quality Assessor).
*   **Semantic Compression:** Querying Axon for AST boundaries and using local LLMs to generate "Token-Optimized Semantic Skeletons" (TOSS) and business logic summaries.
*   **Vulnerability Detection:** Applying LLM-driven pattern recognition over Axon's extracted control/data flows to detect logical flaws and OWASP vulnerabilities.
*   **Verification Loop:** Proposing code changes, instructing Axon to re-index the modified files, and verifying structural integrity post-modification.

### 2. Evolution Plan for Axon (Layer 1)

Axon must evolve to support CodeLynx's requirements for speed, scalability, and deterministic accuracy.

**Phase 1.1: Fix Current Bottlenecks (Immediate)**
*   **Parameterized Cypher:** Replace all string interpolation in `kuzu_backend.py` with parameterized queries to prevent Cypher injection (resolves P0 issue).
*   **Incremental Indexing:** Replace the blocking 30-second `run_pipeline(full=True)` polling mechanism. Implement OS-level file watching (e.g., `watchfiles`). On file change:
    1.  `DETACH DELETE` nodes belonging exclusively to the changed file.
    2.  Re-parse only the changed file.
    3.  `MERGE` new nodes and edges.
*   **Scope Resolution Tiebreakers:** Modify `calls.py` to prefer nearest-neighbor or explicit import paths over "shortest file path" to reduce incorrect `CALLS` edge assignments.

**Phase 1.2: Expand Data Extraction (Short-Term)**
*   **Merge Community Parsers:** Integrate PHP, HTML, JSX/React, C#, and Go Tree-sitter parsers from active forks.
*   **Enhance Edge Types:** Move beyond `CALLS`. Implement rudimentary Data Flow edges (`RETURNS_TO`, `PASSED_AS_ARG`) where syntactically inferable, to support CodeLynx's taint analysis.

**Phase 1.3: Migration to Native Execution (Mid-Term)**
*   **Rust Core Rewrite:** Python is too slow for parsing 10M+ line codebases and computing large graph diffs. Rewrite the core orchestration loop (Tree-sitter invocation, graph diff calculation, KuzuDB C++ API calls) in Rust.
*   **Python Bindings:** Use `PyO3` to expose the Rust core to the existing Python MCP server, ensuring backward compatibility with CodeLynx.

### 3. Evolution Plan for CodeLynx (Layer 2)

CodeLynx must be structured to consume Axon's output efficiently without exceeding LLM context windows.

**Phase 2.1: The Intermediary Protocol (Immediate)**
*   **Define the Query Interface:** Establish strict schemas for how CodeLynx queries Axon.
    *   `get_subgraph(entry_point, depth=2)` -> Returns JSON schema of nodes/edges.
    *   `get_skeletons(file_path)` -> Returns stripped definitions (classes/functions) without implementation bodies.
    *   `get_raw_implementation(node_id)` -> Returns exact source code for a specific function.

**Phase 2.2: Semantic Compression Engine (Short-Term)**
*   **Implement TOSS:** Build a parallel processing module in CodeLynx. For every node returned by Axon, run a fast, local LLM (e.g., Qwen2.5-Coder) to generate a 1-sentence business logic summary.
*   **Caching:** Store these semantic summaries locally (e.g., in SQLite or as metadata back in KuzuDB if Axon supports arbitrary metadata injection). Invalidate cache based on Axon's file hashes.

**Phase 2.3: Specialized Agent Workflows (Mid-Term)**
*   **Security Agent:** Receives TOSS and an entry point. Queries Axon for the call chain. Reads the summaries. If a sequence looks suspicious (e.g., `Endpoint -> DB_Query` without a `Validate` node), it queries Axon for the raw implementations and executes a deep vulnerability analysis.
*   **Refactor Agent:** Instructed to decouple a module. Queries Axon for all inbound/outbound dependencies of the module. Uses LLM to draft new interfaces.

### 4. Integration Efficiency (The Connection Layer)

To ensure the connection between Axon and CodeLynx is not a bottleneck:

*   **Communication Standard:** Use the **Model Context Protocol (MCP)**. Axon acts as the MCP Server; CodeLynx acts as the MCP Client.
*   **Context Window Management:** Axon *must never* return raw source code by default. It must return graph topology or stripped structural stubs. CodeLynx must explicitly request raw code for specific nodes (`node_id`) only when the LLM requires deep inspection.
*   **Asynchronous Processing:** CodeLynx must handle Axon queries asynchronously. If CodeLynx requests a blast-radius analysis that takes 2 seconds, the CodeLynx orchestrator must continue evaluating other independent subgraphs in parallel.
