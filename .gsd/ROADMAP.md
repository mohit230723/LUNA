---
milestone: v1.0
version: 1.0.0
updated: 2026-10-15T22:15:00+05:30
---

# Roadmap

> **Current Phase:** 1 - Foundation & Graph Infrastructure
> **Status:** planning

## Must-Haves (from SPEC)

- [ ] FalkorDB multi-graph store with parameterized Cypher queries and isolated graph naming.
- [ ] Synthetic claims domain generator with planted 8-node fraud ring, 4-node decoy family, and GraphRAG ontology.
- [ ] Atlas skill catalog with 7 skills and 6 tools (`ask_graph` + 5 deterministic algorithm tools).
- [ ] Task decomposition and graph-based skill selection logging chosen and rejected candidates.
- [ ] FastMCP per-agent tool scoping over stdio.
- [ ] Private sub-graph slice extraction and sub-agent execution loop drafting findings.
- [ ] Finding promotion validating evidence against private slices into shared run memory.
- [ ] Contradiction detection (`CONFLICTS_WITH`) and resolution with superseded audit state.
- [ ] Human approval gate, idempotent domain action execution, and cross-run learning score update.
- [ ] Cypher "Why?" path query tracing complete decision justifications.
- [ ] FastAPI backend with SSE event streaming and headless CLI runner.
- [ ] Hyperstudio/Obsidian-aesthetic Cytoscape.js interactive graph dashboard.

---

## Phases

### Phase 1: Foundation & Graph Infrastructure
**Status:** ⬜ Not Started  
**Objective:** Establish FalkorDB Docker container, connection/query wrapper (`GraphStore`), synthetic domain generator with planted fraud ring, GraphRAG ontology, `atlas` skill catalog, algorithm tool registry, Ollama LLM client, and task decomposition / skill selection engine.  
**Requirements:** REQ-01, REQ-02, REQ-03, REQ-04, REQ-05, REQ-06, REQ-07, REQ-08  

**Plans:**
- [ ] Plan 1.1: Environment setup, Docker Compose (FalkorDB), schema constants, and `GraphStore` wrapper with test suite.
- [ ] Plan 1.2: Synthetic domain generator (`luna/domain/generate.py`) with planted fraud ring / decoy family, ground truth exporter, and `ontology.json`.
- [ ] Plan 1.3: `atlas` graph seeder (`luna/atlas/seed.py`) with 7 skills, capabilities, dependencies, and tool bindings.
- [ ] Plan 1.4: Tool registry with 5 deterministic graph algorithm tools plus GraphRAG SDK `ask_graph` integration.
- [ ] Plan 1.5: `LLMClient` protocol, `ChatOllama` wrapper with JSON mode, mock client, task decomposition, and `atlas` skill selection queries.

---

### Phase 2: Execution, Isolation & Promotion
**Status:** ⬜ Not Started  
**Objective:** Implement per-agent FastMCP server exposing only equipped skills, k-hop private slice extraction from domain graph into `agent_<run>_<agent>`, sub-agent execution loop with draft findings, and finding promotion engine with strict evidence validation.  
**Requirements:** REQ-09, REQ-10, REQ-11, REQ-12  
**Depends on:** Phase 1  

**Plans:**
- [ ] Plan 2.1: Per-agent FastMCP server & stdio client session builder.
- [ ] Plan 2.2: Sub-graph extraction copying k-hop neighborhoods into private agent graphs.
- [ ] Plan 2.3: Sub-agent execution loop (system prompt fragment + MCP tool calls + draft findings generation).
- [ ] Plan 2.4: Finding promotion engine validating evidence `cid` existence against agent slices before merging to `run_<id>`.

---

### Phase 3: Conflict Resolution & Action Lifecycle
**Status:** ⬜ Not Started  
**Objective:** Automated contradiction detection between promoted findings, main-agent conflict resolution marking losers as `superseded`, human approval gate, idempotent action execution in domain graph, and cross-run learning updates in `atlas`.  
**Requirements:** REQ-13, REQ-14, REQ-15, REQ-16  
**Depends on:** Phase 2  

**Plans:**
- [ ] Plan 3.1: Contradiction detection engine identifying opposing verdicts on identical entities and creating `[:CONFLICTS_WITH]` edges.
- [ ] Plan 3.2: Main agent conflict resolution logic creating `Decision` nodes and marking superseded findings.
- [ ] Plan 3.3: Action proposal, human approval barrier, idempotent customer flagging execution, and ground truth precision/recall evaluation.
- [ ] Plan 3.4: Cross-run learner updating `SUCCEEDED_ON` edge scores in `atlas` based on action outcomes.

---

### Phase 4: Explainability & Backend API
**Status:** ⬜ Not Started  
**Objective:** Single Cypher "Why?" path query engine traversing decisions, findings, evidence, and skill justifications, complete headless CLI demo script (`scripts/demo.py`), and FastAPI backend with SSE streaming for real-time visualization.  
**Requirements:** REQ-17, REQ-18  
**Depends on:** Phase 3  

**Plans:**
- [ ] Plan 4.1: "Why?" path query module returning structured decision provenance graphs.
- [ ] Plan 4.2: End-to-end headless CLI orchestrator runner (`scripts/demo.py`) with replay recording fallback.
- [ ] Plan 4.3: FastAPI application exposing run lifecycle REST endpoints, human approval controls, and SSE stream.

---

### Phase 5: Obsidian UI & Final Polish
**Status:** ⬜ Not Started  
**Objective:** Build high-polish React + Vite + Cytoscape.js dashboard with Hyperstudio/Obsidian dark aesthetic, live run stream visualization, interactive "Why?" inspector, full test suite pass, demo video recording, and hackathon documentation.  
**Requirements:** REQ-19, NFR-01, NFR-05  
**Depends on:** Phase 4  

**Plans:**
- [ ] Plan 5.1: React + Vite web dashboard setup with Cytoscape.js and Obsidian/Hyperstudio design system tokens.
- [ ] Plan 5.2: SSE event subscriber, live agent activity feed, and approval gate modal.
- [ ] Plan 5.3: Interactive graph explorer (domain vs run vs private slice) with "Why?" path highlight.
- [ ] Plan 5.4: End-to-end integration verification, benchmark runs, demo walkthrough recording, and submission README.

---

## Progress Summary

| Phase | Status | Plans | Complete |
|-------|--------|-------|----------|
| 1: Foundation & Graph Infrastructure | ⬜ | 0/5 | 0% |
| 2: Execution, Isolation & Promotion | ⬜ | 0/4 | 0% |
| 3: Conflict Resolution & Action Lifecycle | ⬜ | 0/4 | 0% |
| 4: Explainability & Backend API | ⬜ | 0/3 | 0% |
| 5: Obsidian UI & Final Polish | ⬜ | 0/4 | 0% |

---

## Timeline

| Phase | Started | Completed | Duration |
|-------|---------|-----------|----------|
| 1: Foundation & Graph Infrastructure | — | — | — |
| 2: Execution, Isolation & Promotion | — | — | — |
| 3: Conflict Resolution & Action Lifecycle | — | — | — |
| 4: Explainability & Backend API | — | — | — |
| 5: Obsidian UI & Final Polish | — | — | — |

---

*Last updated: 2026-10-15*
