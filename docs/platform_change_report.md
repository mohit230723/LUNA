# Platform Page & Trace View Change Report

> **LUNA OS Engineering Report**  
> **Scope:** Platform Page Autonomous Case Workspace & Trace View Guided Tour  
> **Status:** Completed & Compile-Verified  

---

## 1. Summary of What Changed

### A. Case Workspace & Ingestion Engine (`/platform`)
1. **Case-Driven Investigation:** The `/platform` route has been converted from a static demo into an end-to-end case investigation workspace. Users can create cases, attach multiple heterogeneous inputs (pasted text briefs, CSV, JSON, JSONL, XLSX, SQLite, TXT, MD), and trigger a full rebuild into an isolated FalkorDB context graph named `ctx_<conversation_id>`.
2. **Real LLM Extraction & Mapping:**
   - **Tabular Mapping:** For relational and tabular inputs, an LLM mapping plan is generated and validated against real column names to assign entity labels, primary IDs, foreign key references, and shared normalized values (Phone, Email, Address, Account).
   - **Text Extraction:** Plain text and markdown chunks (max 1500 chars with 200 char overlap) are extracted with exact quote grounding. If extracted entity or relationship quotes cannot be matched as substrings within the source chunk, they are dropped with audit counters.
   - **Deterministic Entity Resolution:** Rapidfuzz fuzzy matching (token set ratio $\ge 92$) deduplicates entities while preserving alias lists and source provenance. Borderline matches ($80 \le \text{score} < 92$) create `POSSIBLY_SAME_AS` edges for investigator visibility.
   - **Disk Caching:** Extracted chunks and table plans are cached on disk under `data/cases/<id>/cache/<sha256>.json` to ensure instantaneous, token-efficient rebuilds for unchanged sources.
3. **Multi-Agent Investigation Pipeline:**
   - **Orchestration Stages:** Question $\rightarrow$ **UNDERSTOOD** $\rightarrow$ **RESOLVED MENTIONS** (with interactive `needs_input` disambiguation when ambiguous) $\rightarrow$ **PLANNED** $\rightarrow$ **SKILLS ASSIGNED** (Atlas catalog graph query matching capabilities) $\rightarrow$ **AGENTS WORKING** $\rightarrow$ **VERIFIED** $\rightarrow$ **ANSWER**.
   - **Subagent Slice Isolation:** Each investigator agent receives an extracted private k-hop subgraph slice (`agent_<run>_<agent>`) and executes an LLM tool loop against domain-agnostic context graph tools (`neighbors`, `paths_between`, `shortest_path`, `shared_attributes`, `common_neighbors`, `cluster_of`, `central_nodes`, `timeline`, `source_mentions`, `ask_graph`).
   - **Traversal Recording:** Every edge traversed is logged with provenance metadata and human-readable descriptive notes via `TraversalRecorder`.
   - **Provenance Barrier Verification:** `promote_findings` validates that all evidence CIDs exist in the agent's slice, were observed in `ToolCallLog`, and that all path hops exist as real edges before promotion. Superseded findings are preserved via `SUPERSEDES` links.
   - **Grounded Answer Synthesis:** The final answer is synthesized from verified active findings only, with `[[cid]]` entity citations rendered as clickable interactive chips in the UI.

### B. Trace View Guided Tour (`/platform/:conversationId/trace/:runId`)
1. **Whole-Subgraph Overview:**
   - Displays the complete investigation subgraph used by the agents.
   - Signals path nodes and path edges with Signal White highlights ($2.5\text{px}$ edges), while non-path nodes render at 70% opacity and context nodes at 40% opacity.
   - Layout engine supports **Layered** (Dagre LR with $170\text{px}$ rank separation), **Radial** (Concentric centered on the origin node), and **Force** (CoSE with $12,000$ node repulsion).
   - Label placement fixes: all labels rendered below nodes with high-contrast rounded-rectangle backgrounds, preventing label clipping and overlapping.
2. **Interactive Guided Tour Walkthrough:**
   - Manual, step-by-step tour advances on Next / Prev buttons, tick track clicks, and keyboard shortcuts (`Space` / `Enter` / `ArrowRight` / `ArrowLeft`).
   - Entrance animation smoothly slides the left pane out ($320\text{px} \rightarrow 0\text{px}$ over $350\text{ms}$) with a `ResizeObserver` tracking canvas geometry.
   - The camera centers and zooms on each focused node ($z = \text{clamp}(120 / \text{nodeSizePx}, 1.6, 3.2)$) over an adaptive duration ($600\text{ms} \dots 1100\text{ms}$) with cubic-bezier easing.
   - A floating `StepCard` on canvas top-center displays step counter (`STEP 03 / 06`), tool/agent tags, transition lines, properties grid, and source quotations.
   - Stop 0 represents START (path origin node), followed by steps $1 \dots N$.
   - Accessible and compliant with `prefers-reduced-motion: reduce`.

### C. Live Backend & UI Hardening
1. **Blocking LLM Card:** If no LLM provider is connected or reachable on mount, the Platform page renders a blocking card with setup instructions and `.env` guidance.
2. **Removed Obsolete Controls:** Removed pack selector, Build pack switcher, mock/scripted mode toggle, strict LLM toggle, mock data labels, and static example chips. All suggestions are dynamically generated from active context graph entities.

---

## 2. Name Mappings & Adaptations

| Changer Request Concept | Actual Repository Name / Implementation | Rationale |
|---|---|---|
| `OllamaClient` | `OllamaLLM` (aliased as `OllamaClient`) | Provided backward-compatible alias in `luna/llm/client.py` and `luna/llm/factory.py`. |
| Case Storage | `luna/cases/store.py` (`CaseStore`) on `conversations` graph | Reused existing `conversations` FalkorDB graph; extended with `HAS_SOURCE` edges and `:Source` nodes. |
| Cases API | `/api/chat/conversations` | Preserved existing URL namespace while presenting as "CASES" throughout the UI. |
| Ingestion Pipeline | `luna/ingest/` package | Structured into `chunker.py`, `parsers.py`, `mapper.py`, `extract.py`, `resolve.py`, `loader.py`, `summary.py`, `builder.py`. |
| Investigation Pipeline | `luna/investigate/` package | Structured into `tools.py`, `recorder.py`, `seed.py`, `pipeline.py`, `trace.py`. |
| Trace Mode | `TraceResponse.mode = 'traversal'` | Contract updated to reflect pure traversal mode with path steps and primary tour. |

---

## 3. Key Design Decisions

1. **Strictly Parameterized Cypher:** All queries across `CaseStore`, `loader.py`, `pipeline.py`, and `tools.py` use parameterized Cypher with allowlisted node labels and regex-sanitized identifiers (`^[A-Za-z][A-Za-z0-9_]{0,40}$`).
2. **Anti-Hallucination Barrier:** Text extraction enforces exact substring matching of evidence quotes. Any claims not grounded in source text are filtered out during ingestion. During investigation, claims must cite evidence CIDs present in `ToolCallLog`.
3. **Single State Source in UI:** State transitions on the Platform page are driven directly from `CaseDetail.status` (`draft` | `building` | `ready` | `stale` | `failed`).
4. **Tour Stop Coordinate Model:** Stop 0 represents START (focused on step 1's origin node). Stops $1 \dots N$ focus on step targets. Total stops = $N + 1$. Current stop index and tick marks align 1:1.
5. **Hyperstudio Design System Fidelity:** Maintained strict adherence to `tokens.css`: only predefined Obsidian, Carbon, Graphite, Iron, Smoke, Ash, Chalk, Signal White, Pulse Green, and Compass Gold; 1px hairlines; zero box shadows; zero blur filters.

---

## 4. Scope Decisions & Items Not Done

1. **Part 3.10 Database Connection:**
   - In accordance with Part 3.10 ("OPTIONAL, LAST: database connection ... if you skip it, do not show the tab at all"), direct remote database connection (PostgreSQL/MySQL DSN introspection via SQLAlchemy) was deferred to keep the focus on robust multi-format file ingestion, LLM tool loops, and guided trace visualization.
   - The UI includes only the **PASTE TEXT** and **UPLOAD FILES** tabs.
2. **Automated Tests:**
   - Per Part 0 instructions ("Do NOT write or edit automated tests in this task; the owner will test manually. Do not spend effort repairing existing tests that fail only because static fixtures were intentionally removed"), tests were not modified.
   - Production code passed `npm run build` (`tsc && vite build`) with exit code 0, and all Python modules passed import checks.

---

## 5. Verification Summary

- **Frontend Compilation:** `npm run build` in `d:\LUNA\ui` succeeded with 0 errors (Vite production bundle generated in 15.24s).
- **Backend Import Verification:** `python -c "import luna.api.app; import luna.llm; import luna.ingest.builder; import luna.investigate.pipeline; import luna.cases.store; print('ALL PYTHON IMPORTS SUCCEEDED!')"` executed with exit code 0.
