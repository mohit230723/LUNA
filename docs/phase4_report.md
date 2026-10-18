# LUNA OS — Phase 4 Engineering & Verification Report
**Date:** October 18, 2026  
**Workspace:** `d:\LUNA`  
**Environment:** Python 3.12 (Windows), FalkorDB (Docker), Node v22.15.0, Vite 6, React 18, TypeScript 5.7  
**Commits:**
- `a407ac5` `feat(P1): implement explain why engine and persist skill assignment provenance`
- `f410bb9` `feat(P2): implement LunaPipeline orchestrator with parallel execution and concurrency safety`
- `1429d4e` `feat(P3): implement demo script and deterministic replay engine`
- `7ce8e13` `feat(P4): implement FastAPI backend with SSE streaming and graph inspection API`
- `e6c14b9` `feat(P5): implement Obsidian-themed investigative graph UI with replay mode`

---

## Executive Summary

Phase 4 completes the transition of LUNA OS from an agentic graph toolkit into a production-ready, autonomous, multi-agent investigative operating system. It delivers:
1. **Explain ("Why?") Engine (P1):** End-to-end provenance reconstruction traversing the domain and atlas graphs to generate human-readable justifications with complete evidence subgraphs.
2. **Autonomous Pipeline Orchestrator (P2):** Thread-safe 9-phase orchestrator supporting multi-agent concurrent investigations, reputation scoring, per-customer side resolution, corroboration gating, and human approval barriers.
3. **Demo Script & Deterministic Replay Engine (P3):** CLI orchestrator with support for live Ollama LLM execution, scripted simulation, and zero-deviation deterministic event replay with 100% precision and recall on fraud rings.
4. **FastAPI Streaming Backend (P4):** REST and Server-Sent Events (SSE) server with keepalives, `Last-Event-ID` connection resuming, parameterized query graph inspection, and approval endpoints.
5. **Investigative Graph UI (P5):** High-density, Obsidian-themed React/TypeScript single-page application powered by Cytoscape.js, featuring live event streams, interactive scrubbable replay, side-resolution comparison cards, and human-in-the-loop action approval.
6. **Comprehensive Verification (P6):** 168 passing automated tests (160 in pytest, 8 in Vitest) with zero mutations to shared graphs and strict parameterized Cypher enforcement.

---

## 1. Architectural Overview

```mermaid
flowchart TD
    subgraph Core ["LUNA OS Core Engine"]
        Seed[Domain Graph / Seeds] --> Pipeline[LunaPipeline Orchestrator]
        Pipeline --> Detect[1. Detect Seeds]
        Detect --> Score[2. Score Reputation]
        Score --> Distribute[3. Distribute Tasks]
        Distribute --> Investigate[4. Parallel Investigation]
        Investigate --> Resolve[5. Per-Customer Side Resolution]
        Resolve --> Corroborate[6. Corroboration Gating]
        Corroborate --> Propose[7. Propose Action]
        Propose --> Gate{Human Approval Gate}
        Gate -->|Approved| Act[8. Execute Action & Update Reputation]
        Gate -->|Rejected| Reject[Action Rejected & Audited]
        Act --> Review[9. Final Review & Metrics]
        Reject --> Review
    end

    subgraph Provenance ["Provenance & Explanation"]
        Pipeline -.-> AtlasGraph[(Atlas Graph: Skills, Agents, Reputation)]
        Pipeline -.-> DomainGraph[(Domain Graph: Customers, Transactions, Devices)]
        Explain[Explain 'Why?' Engine] --> AtlasGraph
        Explain --> DomainGraph
    end

    subgraph Delivery ["Interface & Streaming"]
        Pipeline --> EventQueue[Event Queue]
        EventQueue --> FastAPIServer[FastAPI Backend Server]
        FastAPIServer --> SSE[SSE /api/runs/{id}/events]
        FastAPIServer --> REST[REST API: Approvals, Why, Graphs, Replay]
        SSE --> FrontendUI[Investigative Graph UI (ui/)]
        REST --> FrontendUI
    end
```

---

## 2. Phase 4 Component Implementations

### P1: Explain ("Why?") Engine (`luna/orchestrator/explain.py`)
- **Purpose:** Answers the question: *"Why was this customer flagged, investigated, corroborated, or targeted for an enforcement action?"*
- **Key Classes & Functions:**
  - `CustomerExplanation`: Data class encapsulating customer ID, winning side verdict, corroboration breakdown (distinct skills, active suspicious count, best confidence), supporting findings, superseded findings, action justification, and evidence subgraph.
  - `ExplainResult`: Action-focused explanation containing action type, status, confidence, target customer, and underlying customer explanation.
  - `explain_customer(store, run_id, customer_id, atlas_graph, domain_graph)`: Queries the graph for finding nodes, side resolution decision nodes (`UPHELD`, `SUPERSEDES`), corroboration status, and generates a structured narrative.
  - `explain_action(store, run_id, action_id, ...)`: Resolves action provenance through `Action-[:TARGETS]->Customer`.
- **Skill Provenance Persistence:**
  - During task distribution (`assign_skills`), provenance is recorded: `Agent-[:ASSIGNED_SKILL {task_type, run_id, timestamp}]->Skill`.
- **Cypher Security:** All Cypher queries in `explain.py` are strictly parameterized (`$run_id`, `$customer_id`, `$action_id`) with zero string formatting.

### P2: Pipeline Orchestrator (`luna/orchestrator/pipeline.py`)
- **Lifecycle Phases:**
  1. `detect`: Identifies seed customers via degree centrality or flagged rules.
  2. `score`: Computes baseline skill reputation scores from the Atlas graph.
  3. `distribute`: Decomposes tasks into subtasks and assigns skills using Atlas reputation.
  4. `investigate`: Dispatches agents concurrently (`ThreadPoolExecutor` bounded by `parallel` parameter) with isolation.
  5. `resolve`: Executes H2 Side Resolution per customer. For contested customers, scores sides:
     $$S = 0.5 \cdot \text{conf} + 0.2 \cdot \frac{\min(\text{evid}, 5)}{5} + 0.3 \cdot \text{skill\_score}$$
     Losing findings become `status='superseded'`.
  6. `target`: Evaluates H1 Corroboration. A customer is an action target only if active suspicious findings come from $\ge 2$ distinct skills OR confidence $\ge 0.80$.
  7. `propose`: Creates `Action` node in `PENDING` state with an approval token.
  8. `act`: **STRICT HUMAN GATE.** If `approve_and_finish()` is called without explicit approval, raises `NotApprovedError`. Once approved, executes action and updates skill EMA reputation in Atlas.
  9. `review`: Final run metrics collation and event emission.
- **Concurrency Safety:** Parallel agents run in thread pools without race conditions. Each agent operates on its isolated subtask without mutating shared graph structures during execution.

### P3: Demo Script & Replay Engine (`scripts/demo.py`, `artifacts/replay_recording.json`)
- **CLI Options:**
  - `--scripted`: Runs with `MockLLMClient` (deterministic, zero external dependency).
  - `--live`: Runs with real `OllamaClient` against local model.
  - `--strict`: Enforces strict schema validation on LLM output with retry loop.
  - `--replay`: Plays back recording from `artifacts/replay_recording.json`.
  - `--fast`: Fast replay without artificial sleep delays.
  - `--runs N`: Executes $N$ consecutive runs to demonstrate reputation EMA convergence.
  - `--parallel K`: Number of concurrent investigation workers (default: 3).
- **Deterministic Replay & Snapshot Capture:**
  - Every pipeline event is recorded with sequence number, relative timestamp, phase, and data payload.
  - Captures graph snapshots at key lifecycle milestones (`domain`, `atlas`, `run`), enforcing a safety cap of 500 nodes and 1,500 edges.
  - Test run precision: **1.0**, recall: **1.0** on fraud ring detection scenario.

### P4: FastAPI Backend with SSE Streaming (`luna/api/app.py`)
- **Endpoints:**
  - `POST /api/runs`: Initiates a new investigation pipeline run in the background.
  - `GET /api/runs/{run_id}`: Fetches run metadata, status, step progress, and actions.
  - `GET /api/runs/{run_id}/events`: Server-Sent Events (SSE) stream.
    - Emits structured events (`event: pipeline_event\ndata: {...}\nid: {seq}\n\n`).
    - Periodic `: keepalive` comments prevent client timeouts.
    - Supports `Last-Event-ID` header to resume interrupted streams without event loss.
  - `POST /api/runs/{run_id}/approve`: Approves a pending action and resumes pipeline execution.
  - `POST /api/runs/{run_id}/reject`: Rejects a pending action with an audit reason.
  - `GET /api/runs/{run_id}/why/{cid}`: Returns structured explanation narrative and evidence subgraph.
  - `GET /api/graphs/{scope}`: Safe graph slice inspector (`run`, `atlas`, `domain`, `agent`).
    - Sanitizes `scope` against `^[A-Za-z0-9_\-]+$`.
    - Enforces hard cap: maximum 500 nodes and 1,500 edges.
  - `GET /api/replay`: Returns recorded demo runs for zero-latency client replay.
  - Static Mount: Mounts `ui/dist` at `/` when built, serving the SPA directly.

### P5: Investigative Graph UI (`ui/`)
- **Technology Stack:** Vite 6, React 18, TypeScript 5.7, Cytoscape.js 3.30, Lucide React icons.
- **Obsidian / Hyperstudio Aesthetics:**
  - Dark Canvas: `#090d13`, Surface: `#0d1117`, Panels: `#161b22`, Borders: `#30363d`.
  - Accents: Electric Cyan `#39c5cf`, Blue `#58a6ff`, Crimson Warning `#f85149`, Emerald Success `#3fb950`.
  - Typography: Plus Jakarta Sans for UI headers, JetBrains Mono for data tables and graph labels.
- **Key Modules:**
  - `Header.tsx`: Stepper timeline (9 phases), run selector, play/pause, scrub slider, speed multiplier (`1x`, `2x`, `5x`), mode toggle (`LIVE` vs `REPLAY`).
  - `GraphCanvas.tsx`: Interactive Cytoscape graph canvas supporting scope filtering (`run`, `atlas`, `domain`, `agent`), COSE force-directed layout, node shape mappings (diamond customers, round-rect findings, hexagon actions), dimmed superseded nodes, and glowing evidence paths.
  - `FindingsTable.tsx`: Live findings feed with search, status filters (`Active` vs `Superseded`), verdict badges, and confidence meters.
  - `DecisionPanel.tsx`: Contested customer side resolution cards (Side A vs Side B score breakdown), corroboration status, and interactive **Approve** and **Reject** buttons with instant feedback.
  - `WhyExplanationModal.tsx`: Comprehensive modal displaying narrative evidence chain, distinct skills, confidence levels, superseded findings, and an action button to highlight the evidence subgraph directly in Cytoscape.
  - `pipelineReducer.ts`: Pure state reducer processing SSE events and replay ticks deterministically.

---

## 3. Test Matrix & Verification

### Automated Test Suites
| Suite | File | Tests | Status | Duration |
| :--- | :--- | :---: | :---: | :---: |
| **API Endpoints & SSE** | `tests/test_api.py` | 9 | PASS | 38.76s |
| **Explain "Why?" Engine** | `tests/test_explain.py` | 6 | PASS | 2.10s |
| **Pipeline Orchestrator** | `tests/test_pipeline.py` | 10 | PASS | 28.40s |
| **Demo Script & Replay** | `tests/test_demo.py` | 3 | PASS | 1.85s |
| **UI State Reducer** | `ui/src/test/pipelineReducer.test.ts` | 6 | PASS | 18ms |
| **UI Graph Transformer** | `ui/src/test/cytoscapeStyles.test.ts` | 2 | PASS | 8ms |
| **Core & Hardening (F1-F14, H1-H8)** | `tests/test_*.py` | 132 | PASS | ~110s |
| **Total** | **All Modules** | **168** | **ALL GREEN** | **~3m 08s** |

### Verified Security & Concurrency Properties
1. **Parameterized Cypher Only:** All graph store queries utilize parameter maps. Zero unvalidated string interpolation in Cypher queries.
2. **Graph Scope Protection:** Scope parameters validated with regex allowlist `^[A-Za-z0-9_\-]+$`.
3. **Graph Inspection Cap:** Capped at 500 nodes and 1,500 edges to prevent memory exhaustion and browser freezes.
4. **Human Approval Enforcement:** Attempting to execute proposed actions without explicit approval raises `NotApprovedError` and fails closed.
5. **Zero Mutation of Shared Graphs in Tests:** All integration tests utilize `live_store` with unique temporary graph prefixes (`tmp_domain_*`, `tmp_atlas_*`) dropped on teardown.

---

## 4. Runbook & Operator Instructions

### Prerequisites
- Python 3.12 with dependencies installed: `pip install -e .`
- Node.js v20+ with npm: `cd ui && npm install`
- FalkorDB running in Docker on port `6379`:
  ```bash
  docker compose up -d
  ```

### 1. Running the CLI Demo
```bash
# Run deterministic scripted demo (zero LLM requirement)
python scripts/demo.py --scripted

# Run live with local Ollama
python scripts/demo.py --live --strict

# Play back deterministic replay recording
python scripts/demo.py --replay --fast

# Run multiple iterations to verify reputation EMA convergence
python scripts/demo.py --scripted --runs 3
```

### 2. Running the FastAPI Backend
```bash
# Launch FastAPI server on http://localhost:8000
python -m uvicorn luna.api.app:app --host 0.0.0.0 --port 8000 --reload
```
Interactive OpenAPI documentation is available at `http://localhost:8000/docs`.

### 3. Running the Investigative UI
```bash
# Development mode with Vite hot-reload (proxies /api to localhost:8000)
cd ui
npm run dev

# Production build (automatically mounted at http://localhost:8000/)
npm run build
```

---

## 5. Artifacts & Deliverables Summary
- `luna/orchestrator/explain.py`: Explain engine & provenance reconstruction.
- `luna/orchestrator/pipeline.py`: LunaPipeline 9-phase orchestrator.
- `scripts/demo.py`: Demo CLI with live Ollama, scripted simulation, and replay.
- `artifacts/replay_recording.json`: Deterministic recording artifact.
- `luna/api/app.py`: FastAPI server with SSE streaming and graph APIs.
- `ui/`: Complete Vite + React + TypeScript Cytoscape frontend application.
- `docs/phase4_report.md`: This comprehensive engineering document.
